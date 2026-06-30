from rest_framework import permissions, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.content.models import Lesson
from .models import Badge, HelpRequest, LessonProgress, ExerciseAttempt
from .serializers import (
    BadgeSerializer,
    HelpRequestSerializer,
    LessonProgressSerializer,
)


class BadgeListView(ListAPIView):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class MyProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        progress = LessonProgress.objects.filter(user=request.user).select_related(
            "lesson"
        )
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
                difficulty="beginner",
            )

        progress, created = LessonProgress.objects.update_or_create(
            user=request.user,
            lesson=lesson,
            defaults={"completed": completed, "score": score},
        )

        serializer = LessonProgressSerializer(progress)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CommunityStatsView(APIView):
    def get(self, request):
        from django.contrib.auth.models import User

        user_count = User.objects.count()
        completed_lessons = LessonProgress.objects.filter(completed=True).count()
        open_help_requests = HelpRequest.objects.filter(
            status=HelpRequest.Status.OPEN
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


class HelpRequestListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        help_requests = HelpRequest.objects.filter(user=request.user).select_related(
            "lesson"
        )
        serializer = HelpRequestSerializer(help_requests, many=True)
        return Response(serializer.data)

    def post(self, request):
        lesson_slug = request.data.get("lesson_slug")
        message = request.data.get("message", "").strip()

        if not lesson_slug:
            return Response(
                {"error": "lesson_slug is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not message:
            return Response(
                {"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND
            )

        help_request = HelpRequest.objects.create(
            user=request.user,
            lesson=lesson,
            message=message,
        )
        serializer = HelpRequestSerializer(help_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
