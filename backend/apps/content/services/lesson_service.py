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
        Retrieves a lesson by slug, scoped to the caller's organization.
        Raises Lesson.DoesNotExist if not found or not visible to that organization.

        ``organization`` is the caller's ``organizations.Organization``
        (``user.organization``). ``Lesson.organization`` points at a different
        model, ``content.Organization``, so the two cannot be compared with a
        queryset filter. They are matched by name instead, the same way the
        recommendation engine does. Slugs are unique, so the lesson is looked
        up by slug alone and then checked: lessons with no organization are
        public, and an organization's lessons are only visible to its members.
        """
        lesson = Lesson.objects.select_related("organization").get(slug=slug)
        if (
            organization
            and lesson.organization is not None
            and lesson.organization.name != organization.name
        ):
            raise Lesson.DoesNotExist
        return lesson

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
