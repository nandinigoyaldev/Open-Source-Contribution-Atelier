import logging
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
from .meili_client import get_meili_index

logger = logging.getLogger(__name__)

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
      1. Try Meilisearch for typo-tolerant, relevant full-text search.
      2. If Meilisearch fails or is not available, fall back to Postgres
         Full-Text Search with 'websearch' mode.
      3. If FTS returns nothing, fall back to Trigram similarity on the title.
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
        Build an annotated, ordered queryset or list of SearchDocument objects.
        """
        # 1. Try Meilisearch path
        index = get_meili_index()
        if index:
            try:
                search_options = {
                    "attributesToHighlight": ["title", "description", "body_text"],
                    "highlightStartTag": "<mark>",
                    "highlightEndTag": "</mark>",
                    "limit": 200,
                }
                if content_type_filter:
                    search_options["filter"] = [f"content_type_name = '{content_type_filter}'"]

                res = index.search(q, search_options)
                hits = res.get("hits", [])
                
                if hits:
                    doc_ids = [int(hit["id"]) for hit in hits]
                    docs = {
                        doc.id: doc for doc in SearchDocument.objects.filter(
                            id__in=doc_ids
                        ).select_related("content_type")
                    }
                    
                    ordered_docs = []
                    for hit in hits:
                        doc_id = int(hit["id"])
                        if doc_id in docs:
                            doc = docs[doc_id]
                            formatted = hit.get("_formatted", {})
                            doc.headline_title = formatted.get("title", doc.title)
                            doc.headline_description = formatted.get("description", doc.description)
                            doc.headline_body = formatted.get("body_text", doc.body_text)
                            ordered_docs.append(doc)
                            
                    return ordered_docs
            except Exception as exc:
                logger.warning("Meilisearch search failed, falling back to Postgres: %s", exc)

        # 2. Postgres FTS / Trigram fallback paths
        search_query = SearchQuery(q, search_type="websearch")
        base_qs = SearchDocument.objects.all()

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

