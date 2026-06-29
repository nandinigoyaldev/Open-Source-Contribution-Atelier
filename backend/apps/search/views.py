from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from rest_framework import generics
from rest_framework.response import Response

from .models import SearchDocument
from .serializers import SearchDocumentSerializer


class UnifiedSearchView(generics.ListAPIView):
    """
    Provides a unified search API across all indexed models.
    Supports PostgreSQL Full-Text Search ranking and Trigram Similarity (fuzzy matching/typos).
    """

    serializer_class = SearchDocumentSerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        if not query:
            return SearchDocument.objects.none()

        # 1. Exact/Prefix matching with Full-Text Search
        search_query = SearchQuery(query)
        fts_qs = SearchDocument.objects.filter(search_vector=search_query).annotate(
            rank=SearchRank("search_vector", search_query)
        )

        # 2. Fuzzy matching (typo tolerance) using Trigram Similarity on Title
        trigram_qs = SearchDocument.objects.annotate(
            similarity=TrigramSimilarity("title", query)
        ).filter(similarity__gt=0.3)

        # Combine the results. In a real highly-scaled system we might union them,
        # but for simplicity and maximum relevance we prioritize FTS, then fallback to Trigram.

        if fts_qs.exists():
            return fts_qs.order_by("-rank")[:50]

        return trigram_qs.order_by("-similarity")[:50]
