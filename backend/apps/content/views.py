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
from apps.core.pagination import SecureCursorPagination
from apps.core.permissions import IsLessonUnlocked
from apps.progress.models import LessonProgress
from apps.search.models import SearchDocument

from . import semantic_search
from .models import (
    LearningPath,
    Lesson,
    LessonDraft,
    ModuleDraft,
    Organization,
    QuizDraft,
)
from .serializers import (
    LearningPathSerializer,
    LessonDraftSerializer,
    LessonSearchSerializer,
    LessonSerializer,
    ModuleDraftSerializer,
    OrganizationSerializer,
    QuizDraftSerializer,
)


# --- Helper Functions ---
def get_active_lessons():
    from apps.core.cache.stampede import stampede_protected_get_or_set

    lesson_slugs = stampede_protected_get_or_set(
        "curriculum:slugs:v2",
        lambda: list(Lesson.objects.values_list("slug", flat=True)),
        timeout=60 * 60 * 24,
    )

    if not lesson_slugs:
        return []

    return list(
        Lesson.objects.filter(slug__in=lesson_slugs)
        .prefetch_related("exercises", "prerequisites")
        .all()
    )


# --- Existing Views ---
class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    pagination_class = SecureCursorPagination

    def get_permissions(self):
        from apps.core.permissions import HasPermission

        if self.action in ["create", "bulk_import"]:
            return [permissions.IsAuthenticated(), HasPermission("create_content")]
        elif self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("edit_content")]
        elif self.action in ["destroy"]:
            return [permissions.IsAuthenticated(), HasPermission("delete_content")]
        return [permissions.AllowAny()]

    from rest_framework.decorators import action

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        from .serializers import LessonVersionSerializer

        lesson = self.get_object()
        versions = lesson.versions.all()
        serializer = LessonVersionSerializer(versions, many=True)
        return response.Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="bulk-import")
    def bulk_import(self, request):
        import csv
        import io

        from django.utils.text import slugify

        file_obj = request.FILES.get("file")
        if not file_obj:
            return response.Response(
                {
                    "error": "No file uploaded. Please upload a CSV file under key 'file'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw_bytes = file_obj.read()
            # Handle UTF-8 with BOM or standard UTF-8
            decoded_file = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            return response.Response(
                {
                    "error": f"Invalid file encoding. File must be UTF-8 encoded: {str(exc)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        csv_reader = csv.DictReader(io.StringIO(decoded_file))
        if not csv_reader.fieldnames:
            return response.Response(
                {"error": "CSV file is empty or missing headers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        imported_lessons = []
        errors = []
        rows = list(csv_reader)

        org = (
            getattr(request.user, "organization", None)
            if request.user.is_authenticated
            else None
        )

        for idx, row in enumerate(rows, start=2):  # Row 1 is header
            title = (row.get("title") or row.get("Title") or "").strip()
            summary = (row.get("summary") or row.get("Summary") or "").strip()
            content = (row.get("content") or row.get("Content") or "").strip()
            difficulty = (
                row.get("difficulty") or row.get("Difficulty") or "beginner"
            ).strip()
            category = (row.get("category") or row.get("Category") or "general").strip()
            estimated_minutes = (
                row.get("estimated_minutes") or row.get("Estimated Minutes") or 15
            )

            if not title:
                errors.append({"row": idx, "error": "Missing required field: 'title'"})
                continue

            slug = row.get("slug") or row.get("Slug")
            if slug:
                slug = slug.strip()
            else:
                slug = slugify(title, allow_unicode=True)

            if not slug:
                errors.append(
                    {
                        "row": idx,
                        "title": title,
                        "error": "Could not generate valid slug from title",
                    }
                )
                continue

            try:
                estimated_minutes = int(estimated_minutes)
            except (ValueError, TypeError):
                estimated_minutes = 15

            # Handle existing slug collision
            base_slug = slug
            counter = 1
            while Lesson.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            try:
                lesson = Lesson.objects.create(
                    title=title,
                    slug=slug,
                    summary=summary or title,
                    content=content or title,
                    difficulty=difficulty,
                    category=category,
                    estimated_minutes=estimated_minutes,
                    organization=org,
                )
                imported_lessons.append(LessonSerializer(lesson).data)
            except Exception as e:
                errors.append({"row": idx, "title": title, "error": str(e)})

        status_code = (
            status.HTTP_201_CREATED if imported_lessons else status.HTTP_400_BAD_REQUEST
        )
        return response.Response(
            {
                "message": f"{len(imported_lessons)} lessons imported",
                "imported_count": len(imported_lessons),
                "failed_count": len(errors),
                "total_rows": len(rows),
                "errors": errors,
                "lessons": imported_lessons,
            },
            status=status_code,
        )


class SearchView(views.APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        if not query:
            return response.Response({"lessons": [], "challenges": []})

        # Safe SearchQuery handling for special characters (% _ # + @ etc.)
        try:
            search_query = SearchQuery(query, search_type="websearch")
        except Exception:
            search_query = SearchQuery(query, search_type="raw")

        lesson_ct = ContentType.objects.get_for_model(Lesson)
        challenge_ct = ContentType.objects.get_for_model(Challenge)

        def get_fts_objects(model_class, content_type):
            from django.db import connection

            org = (
                getattr(request.user, "organization", None)
                if request.user.is_authenticated
                else None
            )
            filter_kwargs = {"organization": org} if org else {}

            if connection.vendor != "postgresql":
                return list(
                    model_class.objects.filter(
                        (
                            Q(title__icontains=query) | Q(summary__icontains=query)
                            if hasattr(model_class, "summary")
                            else Q(title__icontains=query)
                        ),
                        **filter_kwargs,
                    )[:50]
                )

            try:
                docs = (
                    SearchDocument.objects.filter(
                        content_type=content_type, search_vector=search_query
                    )
                    .annotate(rank=SearchRank("search_vector", search_query))
                    .order_by("-rank")[:50]
                )
            except Exception:
                docs = SearchDocument.objects.none()

            if not docs.exists():
                try:
                    docs = (
                        SearchDocument.objects.filter(content_type=content_type)
                        .annotate(similarity=TrigramSimilarity("title", query))
                        .filter(similarity__gt=0.2)
                        .order_by("-similarity")[:50]
                    )
                except Exception:
                    docs = SearchDocument.objects.none()

            object_ids = [doc.object_id for doc in docs]
            if object_ids:
                objects = model_class.objects.filter(id__in=object_ids, **filter_kwargs)
                if model_class == Lesson:
                    objects = objects.prefetch_related("exercises", "prerequisites")
                return sorted(objects, key=lambda x: object_ids.index(x.id))

            # Fallback to direct icontains search if FTS / Trigram produced no matches
            objects = model_class.objects.filter(
                (
                    Q(title__icontains=query) | Q(summary__icontains=query)
                    if hasattr(model_class, "summary")
                    else Q(title__icontains=query)
                ),
                **filter_kwargs,
            )[:50]
            if model_class == Lesson:
                objects = objects.prefetch_related("exercises", "prerequisites")
            return list(objects)

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


class ModuleDraftViewSet(viewsets.ModelViewSet):
    queryset = ModuleDraft.objects.prefetch_related("lessons__quizzes").all()
    serializer_class = ModuleDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission

        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), HasPermission("edit_content")]

    from rest_framework.decorators import action

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        modules_data = request.data.get("modules", [])
        for mod_idx, mod_data in enumerate(modules_data):
            mod_id = mod_data.get("id")
            if mod_id:
                ModuleDraft.objects.filter(id=mod_id).update(order=mod_idx)

            lessons_data = mod_data.get("lessons", [])
            for les_idx, les_data in enumerate(lessons_data):
                les_id = les_data.get("id")
                if les_id:
                    LessonDraft.objects.filter(id=les_id).update(
                        order=les_idx, module_id=mod_id if mod_id else None
                    )
        return response.Response({"status": "reordered"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        draft = ModuleDraft.all_objects.filter(pk=pk).first()
        if not draft:
            return response.Response(
                {"detail": f"ModuleDraft with id {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        draft.restore()
        serializer = self.get_serializer(draft)
        return response.Response(serializer.data, status=status.HTTP_200_OK)


class LessonDraftViewSet(viewsets.ModelViewSet):
    queryset = LessonDraft.objects.prefetch_related("quizzes").all()
    serializer_class = LessonDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission

        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), HasPermission("edit_content")]

    from rest_framework.decorators import action

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        draft = LessonDraft.all_objects.filter(pk=pk).first()
        if not draft:
            return response.Response(
                {"detail": f"LessonDraft with id {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        draft.restore()
        serializer = self.get_serializer(draft)
        return response.Response(serializer.data, status=status.HTTP_200_OK)


class DraftRestoreView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission

        return [permissions.IsAuthenticated(), HasPermission("edit_content")]

    def post(self, request, pk):
        draft = (
            LessonDraft.all_objects.filter(pk=pk).first()
            or ModuleDraft.all_objects.filter(pk=pk).first()
        )
        if not draft:
            return response.Response(
                {"detail": f"Draft with id {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        draft.restore()
        if isinstance(draft, LessonDraft):
            serializer = LessonDraftSerializer(draft)
        else:
            serializer = ModuleDraftSerializer(draft)
        return response.Response(serializer.data, status=status.HTTP_200_OK)


class QuizDraftViewSet(viewsets.ModelViewSet):
    queryset = QuizDraft.objects.all()
    serializer_class = QuizDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission

        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), HasPermission("edit_content")]


class LearningPathViewSet(viewsets.ModelViewSet):
    serializer_class = LearningPathSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = "pk"

    def get_queryset(self):
        user = self.request.user
        if (
            user
            and user.is_authenticated
            and (
                getattr(user, "is_superuser", False) or getattr(user, "is_staff", False)
            )
        ):
            return LearningPath.objects.all().prefetch_related("required_roles")
        return LearningPath.objects.filter(is_published=True).prefetch_related(
            "required_roles"
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.has_access(request.user):
            return Response(
                {
                    "detail": "Access restricted by role. Required role missing.",
                    "required_roles": [r.name for r in instance.required_roles.all()],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
