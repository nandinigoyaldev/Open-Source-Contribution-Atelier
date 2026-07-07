from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Min, Sum
from apps.progress.constants import XP_PER_LEVEL
from apps.progress.models import XPEvent
from apps.progress.constants import XP_PER_LEVEL
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from django.http import HttpResponse
from django.core.cache import cache
from apps.content.models import Lesson
from apps.content.serializers import LessonSerializer

from .models import (
    Badge,
    Certificate,
    CodeSubmission,
    ExerciseAttempt,
    HelpRequest,
    LessonBookmark,
    LessonProgress,
    QuizAttempt,
    UserBadge,
)
from .serializers import (
    BadgeSerializer,
    BulkSyncSerializer,
    CertificateVerificationSerializer,
    HelpRequestSerializer,
    LessonProgressCreateSerializer,
    LessonProgressSerializer,
    QuizAttemptSerializer,
)
from .throttles import HelpRequestRateThrottle


@extend_schema(responses=BadgeSerializer(many=True))
class BadgeListView(ListAPIView):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


@extend_schema_view(
    get=extend_schema(responses=LessonProgressSerializer(many=True)),
    post=extend_schema(
        request=LessonProgressCreateSerializer, responses=LessonProgressSerializer
    ),
)
class MyProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        progress = LessonProgress.objects.filter(
            user=request.user, organization=request.user.organization
        ).select_related("lesson")
        serializer = LessonProgressSerializer(progress, many=True)
        return Response(serializer.data)

    def post(self, request):
        lesson_slug = request.data.get("lesson_slug")
        from apps.progress.models import XPMultiplierEvent, LessonProgressSync

        idempotency_key = request.data.get("idempotency_key")

        client_timestamp_ms = request.data.get("client_timestamp")

        multiplier = XPMultiplierEvent.get_active_multiplier()

        base_score = request.data.get("score", 100)
        completed = request.data.get("completed", True)

        try:
            lesson = Lesson.objects.get(
                slug=lesson_slug, organization=request.user.organization
            )
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        client_timestamp_ms = request.data.get("client_timestamp")

        with transaction.atomic():
            # Idempotency: if this (user, lesson, key) was already processed,
            # return existing progress state without re-applying multiplier.
            if idempotency_key:
                sync_row = (
                    LessonProgressSync.objects.select_related("lesson")
                    .filter(
                        user=request.user,
                        lesson=lesson,
                        idempotency_key=idempotency_key,
                    )
                    .first()
                )
                if sync_row is not None:
                    progress, _ = LessonProgress.objects.get_or_create(
                        user=request.user,
                        lesson=lesson,
                        defaults={
                            "organization": request.user.organization,
                            "completed": sync_row.completed,
                            "base_score": sync_row.base_score,
                            "multiplier_applied": sync_row.multiplier_applied,
                            "score": sync_row.score,
                        },
                    )
                    serializer = LessonProgressSerializer(progress)
                    async_task = __import__(
                        "django_q.tasks", fromlist=["async_task"]
                    ).async_task
                    async_task(
                        "apps.progress.tasks.evaluate_user_badges_task",
                        request.user.id,
                    )
                    return Response(
                        serializer.data,
                        status=status.HTTP_200_OK,
                    )

            try:
                progress = LessonProgress.objects.get(user=request.user, lesson=lesson)
                created = False

                skip_update = False
                if client_timestamp_ms:
                    import datetime

                    client_dt = datetime.datetime.fromtimestamp(
                        client_timestamp_ms / 1000.0, tz=datetime.timezone.utc
                    )
                    if progress.updated_at > client_dt:
                        skip_update = True

                if not skip_update and (
                    progress.base_score != base_score or progress.completed != completed
                ):
                    old_score = progress.score
                    progress.completed = completed
                    progress.base_score = base_score
                    progress.multiplier_applied = multiplier
                    progress.score = int(base_score * multiplier)
                    progress.organization = request.user.organization
                    progress.save()

                    # XP side-effect only when we actually applied.
                    xp_delta = progress.score - old_score
                    if xp_delta != 0:
                        XPEvent.objects.create(
                            user=request.user,
                            source_type="lesson",
                            source_id=lesson.id,
                            base_points=base_score,
                            multiplier=multiplier,
                            xp_delta=xp_delta,
                        )

            except LessonProgress.DoesNotExist:
                created = True
                progress = LessonProgress.objects.create(
                    user=request.user,
                    lesson=lesson,
                    completed=completed,
                    base_score=base_score,
                    multiplier_applied=multiplier,
                    score=int(base_score * multiplier),
                    organization=request.user.organization,
                )
                # Record XP event for new progress
                XPEvent.objects.create(
                    user=request.user,
                    source_type="lesson",
                    source_id=lesson.id,
                    base_points=base_score,
                    multiplier=multiplier,
                    xp_delta=progress.score,
                )

            # Write idempotency ledger AFTER progress state is committed.
            if idempotency_key:
                LessonProgressSync.objects.create(
                    user=request.user,
                    lesson=lesson,
                    idempotency_key=idempotency_key,
                    completed=progress.completed,
                    base_score=progress.base_score,
                    multiplier_applied=progress.multiplier_applied,
                    score=progress.score,
                    client_timestamp_ms=client_timestamp_ms,
                    server_updated_at=timezone.now(),
                )

        async_task("apps.progress.tasks.evaluate_user_badges_task", request.user.id)

        serializer = LessonProgressSerializer(progress)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BulkSyncProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BulkSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        synced = []

        from apps.progress.models import XPMultiplierEvent

        multiplier = XPMultiplierEvent.get_active_multiplier()

        with transaction.atomic():
            for item in serializer.validated_data["lessons"]:

                lesson_slug = item["lesson_slug"]
                base_score = item.get("score", 100)
                completed = item.get("completed", True)

                try:
                    lesson = Lesson.objects.get(slug=lesson_slug)
                except Lesson.DoesNotExist:
                    lesson = Lesson.objects.create(
                        slug=lesson_slug,
                        title=lesson_slug.replace("-", " ").title(),
                        summary="Dynamic learning module",
                        content="Dynamic content loaded from local file storage.",
                        difficulty="beginner",
                    )

                try:
                    progress = LessonProgress.objects.get(
                        user=request.user, lesson=lesson
                    )
                    client_timestamp_ms = item.get("client_timestamp")
                    skip_update = False
                    if client_timestamp_ms:
                        import datetime

                        client_dt = datetime.datetime.fromtimestamp(
                            client_timestamp_ms / 1000.0, tz=datetime.timezone.utc
                        )
                        if progress.updated_at > client_dt:
                            skip_update = True

                    if not skip_update and (
                        progress.base_score != base_score
                        or progress.completed != completed
                    ):
                        progress.completed = completed
                        progress.base_score = base_score
                        progress.multiplier_applied = multiplier
                        progress.score = int(base_score * multiplier)
                        progress.save()
                        # Record XP event for bulk sync update
                        XPEvent.objects.create(
                            user=request.user,
                            source_type="lesson",
                            source_id=lesson.id,
                            base_points=base_score,
                            multiplier=multiplier,
                            xp_delta=progress.score,
                        )
                except LessonProgress.DoesNotExist:
                    progress = LessonProgress.objects.create(
                        user=request.user,
                        lesson=lesson,
                        completed=completed,
                        base_score=base_score,
                        multiplier_applied=multiplier,
                        score=int(base_score * multiplier),
                    )

                synced.append(progress.id)

            from django_q.tasks import async_task

            async_task("apps.progress.tasks.evaluate_user_badges_task", request.user.id)

        return Response(
            {"synced_count": len(synced), "progress_ids": synced},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Bulk update lesson progress",
    description="Updates multiple lesson progress states atomically in a single transaction.",
    request=BulkSyncSerializer,
    responses={
        200: OpenApiResponse(
            description="Successful bulk update summary: {success, transaction_outcome, updated_count, updated_ids, metadata}"
        ),
        400: OpenApiResponse(
            description="Validation failures (duplicate entries, invalid lessons, etc.)"
        ),
        500: OpenApiResponse(description="Transaction failures or internal errors"),
    },
)
class BulkProgressUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BulkSyncSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "failed",
                    "validation_failures": serializer.errors,
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data["lessons"]

        from apps.progress.services.progress_batch_service import (
            process_bulk_progress_updates,
            DuplicateEntryException,
            InvalidLessonException,
        )

        try:
            success_ids = process_bulk_progress_updates(request.user, validated_data)
        except DuplicateEntryException as e:
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "failed",
                    "validation_failures": {"duplicate_entries": e.duplicates},
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidLessonException as e:
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "rolled_back",
                    "validation_failures": {"invalid_lessons": e.missing_slugs},
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "rolled_back",
                    "validation_failures": {"exception": str(e)},
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "transaction_outcome": "committed",
                "validation_failures": {},
                "updated_count": len(success_ids),
                "updated_ids": success_ids,
                "metadata": {
                    "synced_at": request.data.get("metadata", {}).get("timestamp", None)
                },
            },
            status=status.HTTP_200_OK,
        )


class CommunityFeedPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


@extend_schema(
    responses=OpenApiResponse(
        description="Paginated community activity feed combining help requests, code submissions, badges, and lesson completions."
    )
)
class CommunityFeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        user_ids = (
            User.objects.filter(
                profile__organization=org,
                is_active=True,
            )
            if org
            else User.objects.filter(is_active=True)
        ).values_list("id", flat=True)

        help_requests = (
            HelpRequest.objects.filter(
                user_id__in=user_ids,
            )
            .select_related("user", "lesson")
            .order_by("-created_at")[:200]
        )

        code_submissions = (
            CodeSubmission.objects.filter(
                user_id__in=user_ids,
            )
            .select_related("user", "exercise")
            .order_by("-created_at")[:200]
        )

        badges = (
            UserBadge.objects.filter(
                user_id__in=user_ids,
            )
            .select_related("user", "badge")
            .order_by("-earned_at")[:200]
        )

        lesson_progress = (
            LessonProgress.objects.filter(
                user_id__in=user_ids,
                completed=True,
            )
            .select_related("user", "lesson")
            .order_by("-updated_at")[:200]
        )

        entries = []

        for hr in help_requests:
            entries.append(
                {
                    "id": f"hr_{hr.id}",
                    "type": "help_request",
                    "user_id": hr.user_id,
                    "username": hr.user.username,
                    "title": f"asked for help on {hr.lesson.title}",
                    "description": hr.message[:200],
                    "created_at": hr.created_at.isoformat(),
                }
            )

        for cs in code_submissions:
            entries.append(
                {
                    "id": f"cs_{cs.id}",
                    "type": "code_submission",
                    "user_id": cs.user_id,
                    "username": cs.user.username,
                    "title": f"submitted code — {cs.title}",
                    "description": cs.description[:200] if cs.description else "",
                    "created_at": cs.created_at.isoformat(),
                }
            )

        for ub in badges:
            entries.append(
                {
                    "id": f"bd_{ub.id}",
                    "type": "badge_earned",
                    "user_id": ub.user_id,
                    "username": ub.user.username,
                    "title": f"earned badge — {ub.badge.name}",
                    "description": ub.badge.description,
                    "created_at": ub.earned_at.isoformat(),
                }
            )

        for lp in lesson_progress:
            entries.append(
                {
                    "id": f"lp_{lp.id}",
                    "type": "lesson_completed",
                    "user_id": lp.user_id,
                    "username": lp.user.username,
                    "title": f"completed lesson — {lp.lesson.title}",
                    "description": f"Scored {lp.score} points",
                    "created_at": lp.updated_at.isoformat(),
                }
            )

        entries.sort(key=lambda e: e["created_at"], reverse=True)

        paginator = CommunityFeedPagination()
        page = paginator.paginate_queryset(entries, request)
        return paginator.get_paginated_response(page)


@extend_schema(
    responses=OpenApiResponse(
        description="Community stats: active_contributors, merged_prs, response_sla, open_requests"
    )
)
class CommunityStatsView(APIView):
    def get(self, request):
        from django.contrib.auth.models import User

        user_count = User.objects.count()
        completed_lessons = LessonProgress.objects.filter(
            organization=request.user.organization,
            completed=True,
        ).count()

        open_help_requests = HelpRequest.objects.filter(
            organization=request.user.organization,
            status=HelpRequest.Status.OPEN,
        ).count()
        active_contributors = 100 + user_count
        merged_prs = 300 + completed_lessons

        return Response(
            {
                "active_contributors": active_contributors,
                "merged_prs": merged_prs,
                "response_sla": "3.5h",
                "open_requests": open_help_requests,
            }
        )


class UserAchievementsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        completed_lessons = LessonProgress.objects.filter(
            user=request.user, completed=True
        ).count()

        exercises_completed = ExerciseAttempt.objects.filter(
            user=request.user, is_correct=True
        ).count()

        help_requests = HelpRequest.objects.filter(user=request.user).count()

        badges = []

        if completed_lessons >= 1:
            badges.append(
                {
                    "name": "First Contribution",
                    "description": "Completed your first lesson",
                }
            )

        if completed_lessons >= 5:
            badges.append(
                {"name": "Consistent Learner", "description": "Completed 5 lessons"}
            )

        if completed_lessons >= 10:
            badges.append(
                {"name": "Knowledge Explorer", "description": "Completed 10 lessons"}
            )

        if exercises_completed >= 5:
            badges.append(
                {"name": "Challenge Solver", "description": "Solved 5 exercises"}
            )

        if help_requests >= 3:
            badges.append(
                {"name": "Community Helper", "description": "Created 3 help requests"}
            )

        return Response({"earned_badges": badges})


@extend_schema_view(
    get=extend_schema(responses=HelpRequestSerializer(many=True)),
    post=extend_schema(request=HelpRequestSerializer, responses=HelpRequestSerializer),
)
class HelpRequestListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            return [HelpRequestRateThrottle()]
        return []

    def get(self, request):
        help_requests = HelpRequest.objects.filter(
            user=request.user,
            organization=request.user.organization,
        ).select_related("lesson")
        serializer = HelpRequestSerializer(help_requests, many=True)
        return Response(serializer.data)

    def post(self, request):
        lesson_slug = request.data.get("lesson_slug")
        message = request.data.get("message", "").strip()

        if not lesson_slug:
            return Response(
                {"error": "lesson_slug is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message:
            return Response(
                {"error": "message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lesson = Lesson.objects.get(
                slug=lesson_slug,
                organization=request.user.organization,
            )
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        help_request = HelpRequest.objects.create(
            user=request.user,
            lesson=lesson,
            message=message,
            organization=request.user.organization,
        )

        serializer = HelpRequestSerializer(help_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IsMentor(BasePermission):
    """
    Grants access only to users who have a MentorProfile.

    This permission is intentionally separate from `is_staff` so that
    regular staff administrators are not automatically treated as mentors,
    and mentors do not need elevated Django permissions.
    """

    message = "You must be a designated mentor to access this resource."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and hasattr(request.user, "mentor_profile"))


class MentorHelpRequestListView(ListAPIView):
    """
    Read-only list of HelpRequest tickets scoped to the requesting mentor's
    assigned lessons.

    Only users with a MentorProfile may access this endpoint. The queryset
    is automatically filtered so a mentor can never see tickets outside their
    assigned module scope.

    GET /api/progress/mentor/help-requests/
    """

    serializer_class = HelpRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsMentor]

    def get_queryset(self):
        assigned = self.request.user.mentor_profile.assigned_lessons.all()
        return (
            HelpRequest.objects.filter(lesson__in=assigned)
            .select_related("user", "lesson")
            .order_by("-created_at")
        )


@extend_schema(
    responses=OpenApiResponse(
        description="Contributor timeline: first_contribution_date, completed_lessons, exercise_attempts, help_requests, contribution_streak"
    )
)
class ContributorTimelineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        completed_lessons = LessonProgress.objects.filter(
            user=request.user, completed=True
        ).count()

        exercise_attempts = ExerciseAttempt.objects.filter(user=request.user).count()

        help_requests = HelpRequest.objects.filter(user=request.user).count()

        return Response(
            {
                "first_contribution_date": request.user.date_joined.date(),
                "completed_lessons": completed_lessons,
                "exercise_attempts": exercise_attempts,
                "help_requests": help_requests,
                "contribution_streak": completed_lessons,
            }
        )


@extend_schema_view(
    post=extend_schema(
        description="Create a quiz attempt. Expected JSON fields: question_id, question_text (optional), selected_answer, correct_answer, is_correct, time_taken_seconds.",
        responses=OpenApiResponse(
            description="Created attempt summary: {id, question_id, is_correct, created_at}"
        ),
    ),
    get=extend_schema(
        description="List quiz attempts and stats. Optional query param: question_id. Returns total_attempts, correct, incorrect, accuracy_percent, attempts array.",
        responses=OpenApiResponse(
            description="Quiz attempts summary and attempts array."
        ),
    ),
)
class QuizAttemptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QuizAttemptSerializer(data=request.data)
        if serializer.is_valid():
            attempt = serializer.save(user=request.user)
            return Response(
                {
                    "id": attempt.id,
                    "question_id": attempt.question_id,
                    "is_correct": attempt.is_correct,
                    "created_at": attempt.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                status=status.HTTP_201_CREATED,
            )
        # If there are field errors, extract the first one generically to match typical client expectations
        # Or return all errors. DRF will return a dict like {"selected_answer": ["This field is required."]}
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        attempts = QuizAttempt.objects.filter(user=request.user)

        question_id = request.query_params.get("question_id")
        if question_id:
            attempts = attempts.filter(question_id=question_id)

        total = attempts.count()
        correct = attempts.filter(is_correct=True).count()
        incorrect = total - correct

        return Response(
            {
                "total_attempts": total,
                "correct": correct,
                "incorrect": incorrect,
                "accuracy_percent": (
                    round((correct / total) * 100, 1) if total > 0 else 0
                ),
                "attempts": QuizAttemptSerializer(attempts, many=True).data,
            }
        )


class CertificateVerificationThrottle(AnonRateThrottle):
    rate = "10/minute"


@extend_schema(responses=CertificateVerificationSerializer)
class CertificateVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CertificateVerificationThrottle]

    def get(self, request, hash):
        try:
            certificate = Certificate.objects.get(verification_hash=hash)
        except Certificate.DoesNotExist:
            return Response(
                {"is_valid": False, "error": "Certificate not found or invalid hash."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CertificateVerificationSerializer(certificate)
        if not certificate.is_active:
            return Response(
                {
                    "is_valid": False,
                    "error": "This certificate has been revoked or deactivated.",
                    "certificate": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"is_valid": True, "certificate": serializer.data},
            status=status.HTTP_200_OK,
        )


class MyCertificateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        certificate = Certificate.objects.filter(user=request.user).first()
        if certificate:
            serializer = CertificateVerificationSerializer(certificate)
            return Response(
                {"has_certificate": True, "certificate": serializer.data},
                status=status.HTTP_200_OK,
            )

        completed_lessons = LessonProgress.objects.filter(
            user=request.user, completed=True
        ).count()
        total_lessons = Lesson.objects.count()

        if total_lessons > 0 and completed_lessons >= total_lessons:
            certificate = Certificate.objects.create(
                user=request.user, course_name="Open Source Contribution Course"
            )
            serializer = CertificateVerificationSerializer(certificate)
            return Response(
                {"has_certificate": True, "certificate": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "has_certificate": False,
                "detail": "Course requirements not met. Complete all lessons to unlock.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@extend_schema(responses=LessonSerializer(many=True))
class RecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        total_lessons_info = Lesson.objects.values("category").annotate(
            total=Count("id"), min_order=Min("order")
        )
        total_map = {
            item["category"]: {"total": item["total"], "min_order": item["min_order"]}
            for item in total_lessons_info
        }

        completed_progress = LessonProgress.objects.filter(user=user, completed=True)
        completed_lessons_per_category = completed_progress.values(
            "lesson__category"
        ).annotate(completed=Count("id"))
        completed_map = {
            item["lesson__category"]: item["completed"]
            for item in completed_lessons_per_category
        }

        category_rates = []
        for category, info in total_map.items():
            completed = completed_map.get(category, 0)
            total = info["total"]
            min_order = info["min_order"]
            rate = completed / total if total > 0 else 0

            if rate < 1.0:
                category_rates.append(
                    {"category": category, "rate": rate, "min_order": min_order}
                )

        if not category_rates:
            return Response([])

        category_rates.sort(key=lambda x: (-x["rate"], x["min_order"]))
        top_category = category_rates[0]["category"]

        completed_lesson_ids = completed_progress.values_list("lesson_id", flat=True)
        recommended_lessons = (
            Lesson.objects.filter(category=top_category)
            .exclude(id__in=completed_lesson_ids)
            .prefetch_related("exercises", "prerequisites")
            .order_by("order")
        )

        serializer = LessonSerializer(recommended_lessons, many=True)
        return Response(serializer.data)


from .models import CodeSubmission, ExerciseAttempt, PeerReview
from .serializers import CodeSubmissionSerializer, PeerReviewSerializer


class CodeSubmissionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        submissions = (
            CodeSubmission.objects.filter(status=CodeSubmission.Status.PENDING_REVIEW)
            .exclude(user=request.user)
            .select_related("user")
        )
        serializer = CodeSubmissionSerializer(submissions, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CodeSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            submission = serializer.save(user=request.user)
            if submission.exercise:
                eligible = (
                    ExerciseAttempt.objects.filter(
                        exercise=submission.exercise, is_correct=True
                    )
                    .values_list("user_id", flat=True)
                    .distinct()
                )
                submission.assigned_reviewers.set(
                    User.objects.filter(id__in=eligible).exclude(id=request.user.id)[:2]
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProgressPDFExportView(APIView):
    """
    Generates and returns a PDF report of the authenticated user's
    progress, achievements, certificates, and coding activity.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.progress.services.pdf_report_service import PDFReportGenerator

        generator = PDFReportGenerator(request.user)
        pdf_bytes = generator.generate()

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="progress_report.pdf"'
        return response


class PeerReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, submission_id):
        submission = get_object_or_404(CodeSubmission, id=submission_id)

        if submission.user == request.user:
            return Response(
                {"error": "Cannot review your own submission"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not submission.assigned_reviewers.filter(id=request.user.id).exists():
            return Response(
                {"error": "You are not assigned to review this submission"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if PeerReview.objects.filter(
            submission=submission, reviewer=request.user
        ).exists():
            return Response(
                {"error": "You have already reviewed this submission"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PeerReviewSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                review = serializer.save(
                    submission=submission, reviewer=request.user, points_earned=10
                )
                review_count = PeerReview.objects.filter(submission=submission).count()
                if review_count >= 2:
                    reviews = list(
                        PeerReview.objects.filter(submission=submission).values_list(
                            "is_approved", flat=True
                        )
                    )
                    if all(reviews):
                        submission.status = CodeSubmission.Status.REVIEWED
                        submission.save(update_fields=["status"])
                        if submission.exercise:
                            ExerciseAttempt.objects.get_or_create(
                                user=submission.user,
                                exercise=submission.exercise,
                                defaults={
                                    "submitted_command": "peer_review_passed",
                                    "is_correct": True,
                                },
                            )
                    elif not all(reviews):
                        submission.status = CodeSubmission.Status.ESCALATED
                        submission.save(update_fields=["status"])
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessonBookmarkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug=None):
        bookmarks = LessonBookmark.objects.filter(user=request.user).select_related(
            "lesson"
        )
        data = [
            {
                "id": b.id,
                "lesson": b.lesson.id,
                "lesson_slug": b.lesson.slug,
                "lesson_title": b.lesson.title,
                "lesson_difficulty": b.lesson.difficulty,
                "lesson_category": getattr(b.lesson, "category", ""),
                "lesson_estimated_minutes": b.lesson.estimated_minutes,
                "lesson_summary": getattr(b.lesson, "summary", ""),
                "created_at": b.created_at.isoformat(),
            }
            for b in bookmarks
        ]
        return Response(data)

    def post(self, request, slug=None):
        lesson = get_object_or_404(Lesson, slug=slug)
        bookmark, created = LessonBookmark.objects.get_or_create(
            user=request.user, lesson=lesson
        )
        return Response(
            {"status": "added"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, slug=None):
        bookmark = get_object_or_404(
            LessonBookmark, user=request.user, lesson__slug=slug
        )
        bookmark.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ReadingProgressView(APIView):
    """
    Saves and retrieves the user's reading position in a lesson using the Redis cache.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lesson_slug = request.query_params.get("lesson")
        if not lesson_slug:
            return Response({"error": "Lesson slug required"}, status=status.HTTP_400_BAD_REQUEST)
        
        cache_key = f"reading_progress_{request.user.id}_{lesson_slug}"
        progress = cache.get(cache_key, 0)
        return Response({"progress": progress})

    def post(self, request):
        lesson_slug = request.data.get("lesson")
        progress = request.data.get("progress")
        
        if not lesson_slug or progress is None:
            return Response({"error": "Lesson slug and progress required"}, status=status.HTTP_400_BAD_REQUEST)
            
        cache_key = f"reading_progress_{request.user.id}_{lesson_slug}"
        # Store for 30 days
        cache.set(cache_key, progress, timeout=60 * 60 * 24 * 30)
        return Response({"status": "success", "progress": progress})
