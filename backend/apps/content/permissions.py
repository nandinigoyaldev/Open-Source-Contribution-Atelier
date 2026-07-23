from rest_framework.permissions import BasePermission
from .models import Lesson
from apps.progress.models import LessonProgress


class IsLessonUnlocked(BasePermission):
    """
    Check if user has completed prerequisites for a lesson.
    """

    def has_permission(self, request, view):
        # Get lesson slug from URL
        lesson_slug = view.kwargs.get("slug")
        user = request.user

        if not user or not user.is_authenticated:
            return False

        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            return False

        # If no prerequisites, lesson is accessible
        if not hasattr(lesson, "prerequisites") or not lesson.prerequisites.exists():
            return True

        # Get user's completed lessons
        completed_lessons = LessonProgress.objects.filter(
            user=user, lesson__in=lesson.prerequisites.all(), completed=True
        ).values_list("lesson_id", flat=True)

        # Check if ALL prerequisites are completed
        for prereq in lesson.prerequisites.all():
            if prereq.id not in completed_lessons:
                return False

        return True
