from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from rest_framework import generics
from rest_framework.response import Response
from django.utils.dateparse import parse_date

from .models import SearchDocument
from apps.content.models import Lesson
from .serializers import SearchDocumentSerializer


class UnifiedSearchView(generics.ListAPIView):
    """
    Provides a unified search API across all indexed models.
    Supports PostgreSQL Full-Text Search, Trigram Similarity, and Advanced Filters.
    """

    serializer_class = SearchDocumentSerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        difficulty = self.request.query_params.get("difficulty")
        date_added = self.request.query_params.get("date_added")
        
        # Start with all search documents
        qs = SearchDocument.objects.all()

        # --- 1. Filter by Date ---
        # SearchDocument has a 'created_at' field we can use
        if date_added:
            parsed_date = parse_date(date_added)
            if parsed_date:
                qs = qs.filter(created_at__date=parsed_date)

        # --- 2. Filter by Difficulty ---
        # Difficulty lives in the Lesson model. We find matching lessons first.
        if difficulty:
            lesson_ct = ContentType.objects.get_for_model(Lesson)
            valid_lesson_ids = Lesson.objects.filter(difficulty__iexact=difficulty).values_list('id', flat=True)
            # Filter documents to only include those pointing to the valid lessons
            qs = qs.filter(content_type=lesson_ct, object_id__in=valid_lesson_ids)

        # Require at least one filter or search query
        if not query and not difficulty and not date_added:
            return SearchDocument.objects.none()

        # --- 3. Apply Text Search ---
        if query:
            search_query = SearchQuery(query)
            fts_qs = qs.filter(search_vector=search_query).annotate(
                rank=SearchRank("search_vector", search_query)
            )
            trigram_qs = qs.annotate(
                similarity=TrigramSimilarity("title", query)
            ).filter(similarity__gt=0.3)

            if fts_qs.exists():
                return fts_qs.order_by("-rank")[:50]
            return trigram_qs.order_by("-similarity")[:50]
        
        # If only filters were applied (no text query), return latest matches
        return qs.order_by('-created_at')[:50]