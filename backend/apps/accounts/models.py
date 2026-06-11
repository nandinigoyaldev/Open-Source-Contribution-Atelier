from django.conf import settings
from django.db import models

from apps.content.models import Lesson


class MentorProfile(models.Model):
    """
    Extends the built-in User with mentor-specific scope data.

    Each mentor is assigned zero or more Lessons they are responsible for.
    Only HelpRequest tickets whose lesson appears in `assigned_lessons` will be
    visible to that mentor through the mentor-scoped API endpoint.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentor_profile",
    )
    assigned_lessons = models.ManyToManyField(
        Lesson,
        blank=True,
        related_name="assigned_mentors",
        help_text="Lessons this mentor is authorised to review support tickets for.",
    )

    def __str__(self) -> str:
        return f"MentorProfile({self.user.username})"
