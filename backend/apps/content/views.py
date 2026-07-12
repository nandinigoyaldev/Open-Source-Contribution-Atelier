from io import BytesIO

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
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.progress.models import LessonProgress
from apps.search.models import SearchDocument

from . import semantic_search
from .models import Lesson, Organization
from .permissions import IsLessonUnlocked
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
class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer

    def get_permissions(self):
        from apps.rbac.permissions import HasPermission

        if self.action in ["create"]:
            return [permissions.IsAuthenticated(), HasPermission("create_content")]
        elif self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("edit_content")]
        elif self.action in ["destroy"]:
            return [permissions.IsAuthenticated(), HasPermission("delete_content")]
        return [permissions.AllowAny()]

    def list(self, request, *args, **kwargs):
        lessons = get_active_lessons()
        serializer = self.get_serializer(lessons, many=True)
        return response.Response(serializer.data)

    from rest_framework.decorators import action

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        from .serializers import LessonVersionSerializer

        lesson = self.get_object()
        versions = lesson.versions.all()
        serializer = LessonVersionSerializer(versions, many=True)
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
            from django.db import connection

            org = getattr(request.user, "organization", None)
            if not org:
                return []
            if connection.vendor != "postgresql":
                return list(
                    model_class.objects.filter(
                        title__icontains=query, organization=org
                    )[:50]
                )
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

            org = getattr(request.user, "organization", None)
            if not org:
                return []
            objects = model_class.objects.filter(id__in=object_ids, organization=org)
            if model_class == Lesson:
                objects = objects.prefetch_related("exercises", "prerequisites")
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
        org = getattr(request.user, "organization", None)
        if not org:
            return response.Response({"query": query, "results": []})

        lessons = (
            Lesson.objects.filter(
                embedding__isnull=False,
                organization=org,
            )
            .annotate(trigram_similarity=TrigramSimilarity("title", query))
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
                    "readingTime": lesson.reading_time,
                    "order": lesson.order,
                    "exerciseCount": len(lesson.exercises.all()),
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


class LessonAccessCheckView(views.APIView):
    """
    Check if user can access a lesson.
    """

    permission_classes = [IsLessonUnlocked]

    def get(self, request, slug):
        return Response(
            {"has_access": True, "message": "You have access to this lesson"}
        )


import json
import os

from django.conf import settings


class QuizDetailView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, quiz_id):
        # Look for quizzes.json in the data directory
        quizzes_file = os.path.join(settings.BASE_DIR, "data", "quizzes.json")
        try:
            with open(quizzes_file, "r") as f:
                quizzes = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return response.Response(
                {"error": "Quizzes data not available"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        quiz_data = quizzes.get(quiz_id)
        if not quiz_data:
            return response.Response(
                {"error": "Quiz not found"}, status=status.HTTP_404_NOT_FOUND
            )

        return response.Response(quiz_data)


# --- Lesson Feedback Views ---
from django.db.models import Count
from django.db.models.functions import Coalesce

from .models import Lesson, LessonFeedback
from .serializers import (
    LessonFeedbackCreateSerializer,
    LessonFeedbackMetricsSerializer,
    LessonFeedbackSerializer,
)


class LessonFeedbackListCreateView(generics.ListCreateAPIView):
    """List all feedback for a lesson or create new feedback."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LessonFeedbackCreateSerializer
        return LessonFeedbackSerializer

    def get_queryset(self):
        lesson_slug = self.kwargs.get("lesson_slug")
        return LessonFeedback.objects.filter(
            lesson__slug=lesson_slug, is_deleted=False
        ).select_related("user", "lesson")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["lesson_slug"] = self.kwargs.get("lesson_slug")
        return context

    def perform_create(self, serializer):
        lesson_slug = self.kwargs.get("lesson_slug")
        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            raise serializers.ValidationError({"lesson": "Lesson not found."})
        serializer.save(user=self.request.user, lesson=lesson)


class LessonFeedbackRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific feedback entry."""

    serializer_class = LessonFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LessonFeedback.objects.filter(
            user=self.request.user,
            is_deleted=False,
        ).select_related("user", "lesson")

    def perform_destroy(self, instance):
        instance.delete()


class LessonFeedbackMetricsView(views.APIView):
    """Get aggregated feedback metrics for a lesson."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, lesson_slug):
        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            return response.Response(
                {"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND
            )

        feedbacks = LessonFeedback.objects.filter(lesson=lesson, is_deleted=False)

        total_count = feedbacks.count()

        if total_count == 0:
            metrics = {
                "lesson_slug": lesson_slug,
                "average_rating": 0.0,
                "total_count": 0,
                "rating_distribution": {
                    "1": 0,
                    "2": 0,
                    "3": 0,
                    "4": 0,
                    "5": 0,
                },
            }
        else:
            # Calculate average rating
            total_rating = sum(f.rating for f in feedbacks)
            average_rating = total_rating / total_count

            # Calculate rating distribution
            distribution = {str(i): 0 for i in range(1, 6)}
            for fb in feedbacks:
                distribution[str(fb.rating)] += 1

            metrics = {
                "lesson_slug": lesson_slug,
                "average_rating": round(average_rating, 2),
                "total_count": total_count,
                "rating_distribution": distribution,
            }

        serializer = LessonFeedbackMetricsSerializer(data=metrics)
        serializer.is_valid(raise_exception=True)
        return response.Response(serializer.data)


class UserLessonFeedbackView(views.APIView):
    """Get the current user's feedback for a specific lesson."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_slug):
        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            return response.Response(
                {"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            feedback = LessonFeedback.objects.get(
                user=request.user, lesson=lesson, is_deleted=False
            )
            serializer = LessonFeedbackSerializer(feedback)
            return response.Response(serializer.data)
        except LessonFeedback.DoesNotExist:
            return response.Response(
                {"error": "No feedback found for this lesson"},
                status=status.HTTP_404_NOT_FOUND,
            )
