from typing import Optional
from apps.content.models import Lesson


class LessonService:
    """
    Domain service for Lesson operations.
    Acts as the single point of entry for other modules to access content logic,
    preventing direct ORM access and coupling.
    """

    @staticmethod
    def get_lesson_by_slug(slug: str, organization=None) -> Lesson:
        """
        Retrieves a lesson by slug and organization.
        Raises Lesson.DoesNotExist if not found.
        """
        if organization:
            return Lesson.objects.get(slug=slug, organization=organization)
        return Lesson.objects.get(slug=slug)

    @staticmethod
    def get_or_create_dynamic_lesson(slug: str) -> Lesson:
        """
        Retrieves or creates a dynamic lesson for testing or dynamic loading.
        """
        try:
            return Lesson.objects.get(slug=slug)
        except Lesson.DoesNotExist:
            return Lesson.objects.create(
                slug=slug,
                title=slug.replace("-", " ").title(),
                summary="Dynamic learning module",
                content="Dynamic content loaded from local file storage.",
                difficulty="beginner",
            )
