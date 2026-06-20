from django.contrib.auth.models import User
from django.db.models import Sum, Count, Min
from rest_framework import permissions, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (
    Badge,
    HelpRequest,
    LessonProgress,
    ExerciseAttempt,
    QuizAttempt,
    Certificate,
)
from apps.content.models import Lesson
from apps.content.serializers import LessonSerializer
from .serializers import BadgeSerializer, HelpRequestSerializer, LessonProgressSerializer, LessonProgressCreateSerializer, CertificateVerificationSerializer
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from .throttles import HelpRequestRateThrottle
from django.shortcuts import get_object_or_404
from rest_framework.throttling import AnonRateThrottle

@extend_schema(responses=BadgeSerializer(many=True))
class BadgeListView(ListAPIView):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

@extend_schema_view(
    get=extend_schema(responses=LessonProgressSerializer(many=True)),
    post=extend_schema(request=LessonProgressCreateSerializer, responses=LessonProgressSerializer),
)
class MyProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        progress = LessonProgress.objects.filter(user=request.user).select_related("lesson")
        serializer = LessonProgressSerializer(progress, many=True)
        return Response(serializer.data)

    def post(self, request):
        lesson_slug = request.data.get("lesson_slug")
        score = request.data.get("score", 100)
        completed = request.data.get("completed", True)

        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            lesson = Lesson.objects.create(
                slug=lesson_slug,
                title=lesson_slug.replace("-", " ").title(),
                summary="Dynamic learning module",
                content="Dynamic content loaded from local file storage.",
                difficulty="beginner"
            )

        progress, created = LessonProgress.objects.update_or_create(
            user=request.user,
            lesson=lesson,
            defaults={"completed": completed, "score": score}
        )

        from .badge_evaluator import BadgeEvaluator
        BadgeEvaluator.evaluate(request.user)

        serializer = LessonProgressSerializer(progress)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


@extend_schema(responses=OpenApiResponse(description="Community stats summary JSON: active_contributors, merged_prs, response_sla, open_requests"))
class CommunityStatsView(APIView):
    def get(self, request):
        from django.contrib.auth.models import User

        user_count = User.objects.count()
        completed_lessons = LessonProgress.objects.filter(completed=True).count()
        open_help_requests = HelpRequest.objects.filter(status=HelpRequest.Status.OPEN).count()
        active_contributors = 100 + user_count
        merged_prs = 300 + completed_lessons

        return Response({
            "active_contributors": active_contributors,
            "merged_prs": merged_prs,
            "response_sla": "3.5h",
            "open_requests": open_help_requests
        })
    
class UserAchievementsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        completed_lessons = LessonProgress.objects.filter(
            user=request.user,
            completed=True
        ).count()

        exercises_completed = ExerciseAttempt.objects.filter(
            user=request.user,
            is_correct=True
        ).count()

        help_requests = HelpRequest.objects.filter(
            user=request.user
        ).count()

        badges = []

        if completed_lessons >= 1:
            badges.append({
                "name": "First Contribution",
                "description": "Completed your first lesson"
            })

        if completed_lessons >= 5:
            badges.append({
                "name": "Consistent Learner",
                "description": "Completed 5 lessons"
            })

        if completed_lessons >= 10:
            badges.append({
                "name": "Knowledge Explorer",
                "description": "Completed 10 lessons"
            })

        if exercises_completed >= 5:
            badges.append({
                "name": "Challenge Solver",
                "description": "Solved 5 exercises"
            })

        if help_requests >= 3:
            badges.append({
                "name": "Community Helper",
                "description": "Created 3 help requests"
            })

        return Response({
            "earned_badges": badges
        })

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
        help_requests = HelpRequest.objects.filter(user=request.user).select_related("lesson")
        serializer = HelpRequestSerializer(help_requests, many=True)
        return Response(serializer.data)

    def post(self, request):
        lesson_slug = request.data.get("lesson_slug")
        message = request.data.get("message", "").strip()

        if not lesson_slug:
            return Response({"error": "lesson_slug is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not message:
            return Response({"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

        help_request = HelpRequest.objects.create(
            user=request.user,
            lesson=lesson,
            message=message,
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
            HelpRequest.objects
            .filter(lesson__in=assigned)
            .select_related("user", "lesson")
            .order_by("-created_at")
        )


@extend_schema(responses=OpenApiResponse(description="Contributor timeline: first_contribution_date, completed_lessons, exercise_attempts, help_requests, contribution_streak"))   
class ContributorTimelineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        completed_lessons = LessonProgress.objects.filter(
            user=request.user,
            completed=True
        ).count()

        exercise_attempts = ExerciseAttempt.objects.filter(
            user=request.user
        ).count()

        help_requests = HelpRequest.objects.filter(
            user=request.user
        ).count()

        return Response({
            "first_contribution_date": request.user.date_joined.date(),
            "completed_lessons": completed_lessons,
            "exercise_attempts": exercise_attempts,
            "help_requests": help_requests,
            "contribution_streak": completed_lessons,
        })
    
@extend_schema_view(
    post=extend_schema(
        description="Create a quiz attempt. Expected JSON fields: question_id, question_text (optional), selected_answer, correct_answer, is_correct, time_taken_seconds.",
        responses=OpenApiResponse(description="Created attempt summary: {id, question_id, is_correct, created_at}"),
    ),
    get=extend_schema(
        description="List quiz attempts and stats. Optional query param: question_id. Returns total_attempts, correct, incorrect, accuracy_percent, attempts array.",
        responses=OpenApiResponse(description="Quiz attempts summary and attempts array."),
    ),
)
class QuizAttemptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        question_id = request.data.get("question_id")
        question_text = request.data.get("question_text", "")
        selected_answer = request.data.get("selected_answer")
        correct_answer = request.data.get("correct_answer")
        is_correct = request.data.get("is_correct", False)
        time_taken_seconds = request.data.get("time_taken_seconds", 0)

        if not question_id:
            return Response(
                {"error": "question_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if selected_answer is None:
            return Response(
                {"error": "selected_answer is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if correct_answer is None:
            return Response(
                {"error": "correct_answer is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        attempt = QuizAttempt.objects.create(
            user=request.user,
            question_id=question_id,
            question_text=question_text,
            selected_answer=selected_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            time_taken_seconds=time_taken_seconds,
        )

        return Response({
            "id": attempt.id,
            "question_id": attempt.question_id,
            "is_correct": attempt.is_correct,
            "created_at": attempt.created_at,
        }, status=status.HTTP_201_CREATED)

    def get(self, request):
        attempts = QuizAttempt.objects.filter(user=request.user)

        question_id = request.query_params.get("question_id")
        if question_id:
            attempts = attempts.filter(question_id=question_id)

        total = attempts.count()
        correct = attempts.filter(is_correct=True).count()
        incorrect = total - correct

        return Response({
            "total_attempts": total,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy_percent": round((correct / total) * 100, 1) if total > 0 else 0,
            "attempts": list(attempts.values(
                "id", "question_id", "question_text",
                "selected_answer", "correct_answer",
                "is_correct", "time_taken_seconds", "created_at"
            ))
        })

class CertificateVerificationThrottle(AnonRateThrottle):
    rate = '10/minute'

@extend_schema(responses=CertificateVerificationSerializer)
class CertificateVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CertificateVerificationThrottle]

    def get(self, request, hash):
        try:
            certificate = Certificate.objects.get(verification_hash=hash)
        except Certificate.DoesNotExist:
            return Response({
                "is_valid": False,
                "error": "Certificate not found or invalid hash."
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = CertificateVerificationSerializer(certificate)
        if not certificate.is_active:
            return Response({
                "is_valid": False,
                "error": "This certificate has been revoked or deactivated.",
                "certificate": serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            "is_valid": True,
            "certificate": serializer.data
        }, status=status.HTTP_200_OK)

class MyCertificateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        certificate = Certificate.objects.filter(user=request.user).first()
        if certificate:
            serializer = CertificateVerificationSerializer(certificate)
            return Response({
                "has_certificate": True,
                "certificate": serializer.data
            }, status=status.HTTP_200_OK)

        completed_lessons = LessonProgress.objects.filter(user=request.user, completed=True).count()
        total_lessons = Lesson.objects.count()

        if total_lessons > 0 and completed_lessons >= total_lessons:
            certificate = Certificate.objects.create(
                user=request.user,
                course_name="Open Source Contribution Course"
            )
            serializer = CertificateVerificationSerializer(certificate)
            return Response({
                "has_certificate": True,
                "certificate": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "has_certificate": False,
            "detail": "Course requirements not met. Complete all lessons to unlock."
        }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(responses=LessonSerializer(many=True))
class RecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        total_lessons_info = Lesson.objects.values("category").annotate(
            total=Count("id"),
            min_order=Min("order")
        )
        total_map = {
            item["category"]: {"total": item["total"], "min_order": item["min_order"]}
            for item in total_lessons_info
        }

        completed_progress = LessonProgress.objects.filter(user=user, completed=True)
        completed_lessons_per_category = completed_progress.values("lesson__category").annotate(completed=Count("id"))
        completed_map = {item["lesson__category"]: item["completed"] for item in completed_lessons_per_category}

        category_rates = []
        for category, info in total_map.items():
            completed = completed_map.get(category, 0)
            total = info["total"]
            min_order = info["min_order"]
            rate = completed / total if total > 0 else 0

            if rate < 1.0:
                category_rates.append({
                    "category": category,
                    "rate": rate,
                    "min_order": min_order
                })

        if not category_rates:
            return Response([])

        category_rates.sort(key=lambda x: (-x["rate"], x["min_order"]))
        top_category = category_rates[0]["category"]

        completed_lesson_ids = completed_progress.values_list("lesson_id", flat=True)
        recommended_lessons = Lesson.objects.filter(
            category=top_category
        ).exclude(
            id__in=completed_lesson_ids
        ).order_by("order")

        serializer = LessonSerializer(recommended_lessons, many=True)
        return Response(serializer.data)

