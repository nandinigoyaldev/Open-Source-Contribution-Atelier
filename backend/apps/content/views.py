from io import BytesIO

from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.progress.models import LessonProgress
from apps.search.models import SearchDocument
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from rest_framework import (
    filters,
    generics,
    permissions,
    response,
    status,
    views,
    viewsets,
)
from rest_framework.permissions import AllowAny

from . import semantic_search
from .models import Lesson, Organization
from .serializers import (
    LessonSearchSerializer,
    LessonSerializer,
    OrganizationSerializer,
)


# --- Helper Functions ---
def get_active_lessons():
    lessons = cache.get("active_lessons_list")
    if lessons is None:
        lessons = list(
            Lesson.objects.prefetch_related("exercises", "prerequisites").all()
        )
        cache.set("active_lessons_list", lessons, 60 * 60 * 24)
    return lessons


# --- Existing Views ---
class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LessonSerializer

    def list(self, request, *args, **kwargs):
        lessons = get_active_lessons()
        serializer = self.get_serializer(lessons, many=True)
        return response.Response(serializer.data)


class SearchView(views.APIView):
    def get(self, request):
        query = request.GET.get("q", "")
        if not query:
            return response.Response({"lessons": [], "challenges": []})
        search_query = SearchQuery(query)
        lesson_ct = ContentType.objects.get_for_model(Lesson)
        challenge_ct = ContentType.objects.get_for_model(Challenge)

        def get_fts_objects(model_class, content_type):
            docs = (
                SearchDocument.objects.filter(  # type: ignore
                    content_type=content_type, search_vector=search_query
                )
                .annotate(rank=SearchRank("search_vector", search_query))
                .order_by("-rank")[:50]
            )

            if not docs.exists():
                docs = (
                    SearchDocument.objects.filter(content_type=content_type)  # type: ignore
                    .annotate(similarity=TrigramSimilarity("title", query))
                    .filter(similarity__gt=0.3)
                    .order_by("-similarity")[:50]
                )

            object_ids = [doc.object_id for doc in docs]
            if not object_ids:
                return []

            objects = model_class.objects.filter(
                id__in=object_ids, organization=request.user.organization
            )
            # Sort them in the exact order returned by FTS
            ordered_objects = sorted(objects, key=lambda x: object_ids.index(x.id))
            return ordered_objects

        lessons = get_fts_objects(Lesson, lesson_ct)
        challenges = get_fts_objects(Challenge, challenge_ct)

        return response.Response(
            {
                "lessons": LessonSerializer(lessons, many=True).data,
                "challenges": ChallengeSerializer(challenges, many=True).data,
            }
        )


class SemanticSearchView(views.APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        top_k = int(request.GET.get("top_k", 10))

        if not query:
            return response.Response({"query": query, "results": []})

        if not semantic_search.is_available():
            return response.Response(
                {
                    "error": "Semantic search is not available.",
                    "query": query,
                    "results": [],
                },
                status=503,
            )

        # Apply multi-tenant filtering
        lessons = (
            Lesson.objects.filter(
                embedding__isnull=False,
                organization=request.user.organization,
            )
            .annotate(
                trigram_similarity=TrigramSimilarity("title", query)
            )
            .prefetch_related("exercises")
        )
        if not lessons.exists():
            return response.Response({"query": query, "results": []})

        service = semantic_search.SemanticSearchService(list(lessons))
        results = service.search(query, top_k=top_k, min_score=0.15)

        return response.Response(
            {
                "query": query,
                "results": [
                    {
                        "score": r["score"],
                        "lesson": LessonSearchSerializer(r["lesson"]).data,
                    }
                    for r in results
                ],
            }
        )


class RoadmapView(views.APIView):
    """Return ordered curriculum with optional per-user completion state."""

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        lessons = get_active_lessons()

        progress_by_slug = {}

        if request.user and request.user.is_authenticated:
            progress_rows = LessonProgress.objects.filter(
                user=request.user,
                organization=request.user.organization,
                lesson__in=lessons,
            ).select_related("lesson")

            progress_by_slug = {p.lesson.slug: p for p in progress_rows}

        track = []
        completed_count = 0

        for lesson in lessons:
            user_progress = progress_by_slug.get(lesson.slug)
            completed = bool(user_progress and user_progress.completed)
            score = int(user_progress.score) if user_progress else 0

            if completed:
                completed_count += 1

            track.append(
                {
                    "id": lesson.id,
                    "slug": lesson.slug,
                    "title": lesson.title,
                    "summary": lesson.summary,
                    "difficulty": lesson.difficulty,
                    "estimatedMinutes": lesson.estimated_minutes,
                    "order": lesson.order,
                    "exerciseCount": lesson.exercises.count(),
                    "prerequisites": [p.slug for p in lesson.prerequisites.all()],
                    "completed": completed,
                    "score": score,
                }
            )

        return response.Response(
            {
                "track": track,
                "stats": {
                    "total_lessons": len(track),
                    "completed_lessons": completed_count,
                },
            }
        )


# --- New: Organization View ---
class OrganizationListView(generics.ListAPIView):
    queryset = Organization.objects.all()  # type: ignore
    serializer_class = OrganizationSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "date_added", "popularity_score"]
    ordering = ["-popularity_score"]


class LessonPDFView(views.APIView):
    def get(self, request, pk):
        try:
            lesson = Lesson.objects.get(pk=pk)
        except Lesson.DoesNotExist:
            return response.Response(
                {"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND
            )

        buffer = BytesIO()

        doc = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()

        elements = []

        elements.append(Paragraph(lesson.title, styles["Title"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph(f"Difficulty: {lesson.difficulty}", styles["Normal"]))
        elements.append(
            Paragraph(
                f"Estimated Minutes: {lesson.estimated_minutes}", styles["Normal"]
            )
        )
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Summary", styles["Heading2"]))
        elements.append(Paragraph(lesson.summary, styles["BodyText"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Content", styles["Heading2"]))
        elements.append(Paragraph(lesson.content, styles["BodyText"]))
        elements.append(Spacer(1, 12))

        if lesson.learning_objectives:
            elements.append(Paragraph("Learning Objectives", styles["Heading2"]))

            for item in lesson.learning_objectives:
                elements.append(Paragraph(f"- {item}", styles["BodyText"]))

        if lesson.tips:
            elements.append(Paragraph("Tips", styles["Heading2"]))

            for tip in lesson.tips:
                elements.append(Paragraph(f"- {tip}", styles["BodyText"]))

        doc.build(elements)

        pdf = buffer.getvalue()
        buffer.close()

        response_obj = HttpResponse(pdf, content_type="application/pdf")

        response_obj["Content-Disposition"] = (
            f'attachment; filename="{lesson.slug}.pdf"'
        )

        return response_obj
