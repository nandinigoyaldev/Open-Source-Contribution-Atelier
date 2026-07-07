from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import query
from rest_framework import generics
from rest_framework.permissions import AllowAny

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response

from .models import SearchAnalytics, SearchDocument
from .serializers import SearchAnalyticsSerializer, SearchDocumentSerializer
from .utils import get_search_cache_version


class TrackSearchView(generics.CreateAPIView):
    queryset = SearchAnalytics.objects.all()
    serializer_class = SearchAnalyticsSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        ip_address = self.get_client_ip()
        serializer.save(
            user=self.request.user if self.request.user.is_authenticated else None,
            ip_address=ip_address,
        )

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return self.request.META.get("REMOTE_ADDR")


class UnifiedSearchView(generics.ListAPIView):
    """
    Provides a unified search API across all indexed models.
    Supports PostgreSQL Full-Text Search ranking and Trigram Similarity (fuzzy matching/typos).
    """

    serializer_class = SearchDocumentSerializer

    def list(self, request, *args, **kwargs):
        query = self.request.query_params.get("q", "")
        if not query:
            return Response([])

        version = get_search_cache_version()
        cache_key = f"search_api:v{version}:q:{query}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        timeout = getattr(settings, "SEARCH_CACHE_TIMEOUT", 3600)
        cache.set(cache_key, data, timeout=timeout)

        return Response(data)

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        if not query:
            return SearchDocument.objects.none()

        # Exact/Prefix matching with Full-Text Search
        search_query = SearchQuery(query)
        fts_qs = (
            SearchDocument.objects.filter(search_vector=search_query)
            .annotate(rank=SearchRank("search_vector", search_query))
            .distinct()
        )

        # Fuzzy matching (typo tolerance) using Trigram Similarity on Title
        trigram_qs = (
            SearchDocument.objects.annotate(
                similarity=TrigramSimilarity("title", query)
            )
            .filter(similarity__gt=0.3)
            .distinct()
        )

        if fts_qs.exists():
            return fts_qs.order_by("-rank")[:50]

        return trigram_qs.order_by("-similarity")[:50]
