from django.conf import settings
from django.core.cache import cache
from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    SearchRank,
    TrigramSimilarity,
)
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import SearchAnalytics, SearchDocument
from .serializers import SearchAnalyticsSerializer, SearchDocumentSerializer
from .utils import get_search_cache_version

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class SearchPagination(PageNumberPagination):
    """Standard cursor-less pagination for search results."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ---------------------------------------------------------------------------
# Analytics tracking
# ---------------------------------------------------------------------------


class TrackSearchView(generics.CreateAPIView):
    queryset = SearchAnalytics.objects.all()
    serializer_class = SearchAnalyticsSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        ip_address = self._get_client_ip()
        serializer.save(
            user=self.request.user if self.request.user.is_authenticated else None,
            ip_address=ip_address,
        )

    def _get_client_ip(self):
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return self.request.META.get("REMOTE_ADDR")


# ---------------------------------------------------------------------------
# Unified search
# ---------------------------------------------------------------------------

# Options for SearchHeadline — wrap matched tokens in <mark> tags
_HEADLINE_OPTIONS = "StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15"


class UnifiedSearchView(generics.ListAPIView):
    """
    Unified search API across all indexed models.

    Query parameters:
      q         — required — the search term
      type      — optional — filter by content type (lesson, challenge, issue, user …)
      page      — optional — page number (default 1)
      page_size — optional — results per page (default 20, max 100)

    Strategy:
      1. Try PostgreSQL Full-Text Search with 'websearch' mode (handles partial
         words, phrases, negation).  Results are ranked by SearchRank.
      2. If FTS returns nothing, fall back to Trigram similarity on the title
         for typo tolerance (threshold > 0.3).

    Highlights:
      Matched keywords are wrapped in <mark>…</mark> for title, description,
      and body_text via Postgres SearchHeadline.
    """

    serializer_class = SearchDocumentSerializer
    pagination_class = SearchPagination

    # ------------------------------------------------------------------ list

    def list(self, request, *args, **kwargs):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"count": 0, "next": None, "previous": None, "results": []})

        content_type_filter = request.query_params.get("type", "").strip().lower()

        version = get_search_cache_version()
        cache_key = f"search_api:v{version}:q:{q}:type:{content_type_filter}"

        # Only cache un-paginated metadata; actual pages are not cached to
        # keep memory usage bounded.
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        queryset = self._build_queryset(q, content_type_filter)

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Cache the full paginated envelope
            timeout = getattr(settings, "SEARCH_CACHE_TIMEOUT", 3600)
            cache.set(cache_key, response.data, timeout=timeout)
            return response

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        timeout = getattr(settings, "SEARCH_CACHE_TIMEOUT", 3600)
        cache.set(cache_key, data, timeout=timeout)
        return Response(data)

    # ------------------------------------------------------------------ queryset

    def _build_queryset(self, q: str, content_type_filter: str):
        """
        Build an annotated, ordered queryset.

        Uses 'websearch' SearchQuery mode which supports:
          - Partial word matching  (postgres `:*` prefix is used internally)
          - AND / OR / NOT operators
          - Phrase matching ("quoted strings")
        """
        # websearch mode mirrors Google-style query parsing — no need to escape
        search_query = SearchQuery(q, search_type="websearch")

        base_qs = SearchDocument.objects.all()

        # Apply content-type filter (fast: uses the denormalized char field)
        if content_type_filter:
            base_qs = base_qs.filter(content_type_name=content_type_filter)

        # --- FTS path -------------------------------------------------------
        fts_qs = (
            base_qs.filter(search_vector=search_query)
            .annotate(
                rank=SearchRank(
                    "search_vector",
                    search_query,
                    weights=[0.1, 0.4, 0.4, 1.0],  # D, C, B, A
                    cover_density=True,
                ),
                headline_title=SearchHeadline(
                    "title",
                    search_query,
                    config="english",
                    highlight_all=False,
                    options=_HEADLINE_OPTIONS,
                ),
                headline_description=SearchHeadline(
                    "description",
                    search_query,
                    config="english",
                    highlight_all=False,
                    options=_HEADLINE_OPTIONS,
                ),
                headline_body=SearchHeadline(
                    "body_text",
                    search_query,
                    config="english",
                    highlight_all=False,
                    options=_HEADLINE_OPTIONS,
                ),
            )
            .distinct()
        )

        if fts_qs.exists():
            return fts_qs.order_by("-rank")

        # --- Trigram fallback (typo tolerance) ------------------------------
        return (
            base_qs.annotate(similarity=TrigramSimilarity("title", q))
            .filter(similarity__gt=0.25)
            .distinct()
            .order_by("-similarity")
        )
