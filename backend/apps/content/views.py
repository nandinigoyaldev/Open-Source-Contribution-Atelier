from rest_framework import viewsets, views, response, permissions
from django.db.models import Q

from .models import Lesson
from .serializers import LessonSerializer
from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.progress.models import LessonProgress


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Lesson.objects.prefetch_related("exercises").all()
    serializer_class = LessonSerializer


class SearchView(views.APIView):
    def get(self, request):
        query = request.GET.get("q", "")
        if not query:
            return response.Response({"lessons": [], "challenges": []})

        lessons = Lesson.objects.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
        )
        challenges = Challenge.objects.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
        )

        return response.Response(
            {
                "lessons": LessonSerializer(lessons, many=True).data,
                "challenges": ChallengeSerializer(challenges, many=True).data,
            }
        )


class RoadmapView(views.APIView):
    """Return ordered curriculum with optional per-user completion state."""

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        lessons = list(Lesson.objects.prefetch_related("exercises").all())

        progress_by_slug = {}
        if request.user and request.user.is_authenticated:
            progress_rows = LessonProgress.objects.filter(
                user=request.user,
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
                    "estimated_minutes": lesson.estimated_minutes,
                    "order": lesson.order,
                    "exercise_count": lesson.exercises.count(),
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
