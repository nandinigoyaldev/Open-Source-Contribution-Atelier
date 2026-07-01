import uuid

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


class PasswordResetToken(models.Model):
    """
    Secure, single-use password reset token sent to a user's email.

    Tokens expire after settings.PASSWORD_RESET_TIMEOUT_MINUTES (default 15).
    Once used, `is_used` is set to True and the token cannot be reused.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PasswordResetToken(user={self.user.username}, used={self.is_used})"

    def is_expired(self) -> bool:
        """Return True if the token is older than PASSWORD_RESET_TIMEOUT_MINUTES."""
        from datetime import timedelta

        from django.utils import timezone

        timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT_MINUTES", 15)
        return timezone.now() > self.created_at + timedelta(minutes=timeout)


class OTPToken(models.Model):
    """
    Secure OTP token sent to a user's email for verification.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otp_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"OTPToken(user={self.user.username}, used={self.is_used})"


class MagicLinkToken(models.Model):
    """
    Secure, single-use magic link token sent to a user's email for passwordless login.

    Tokens expire after settings.MAGIC_LINK_TIMEOUT_MINUTES (default 15).
    Once used, `is_used` is set to True and the token cannot be reused.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="magic_link_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MagicLinkToken(user={self.user.username}, used={self.is_used})"

    def is_expired(self) -> bool:
        """Return True if the token is older than MAGIC_LINK_TIMEOUT_MINUTES."""
        from datetime import timedelta

        from django.utils import timezone

        timeout = getattr(settings, "MAGIC_LINK_TIMEOUT_MINUTES", 15)
        return timezone.now() > self.created_at + timedelta(minutes=timeout)


def get_timezone_choices():
    from zoneinfo import available_timezones

    return sorted((tz, tz) for tz in available_timezones())


class UserProfile(models.Model):
    """
    Standard user profile linking to the main User model.
    Stores the user's avatar image.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    cover_image = models.ImageField(upload_to="covers/", null=True, blank=True)
    last_password_change = models.DateTimeField(auto_now_add=True)
    timezone = models.CharField(
        max_length=64,
        choices=get_timezone_choices(),
        default="UTC",
    )
    twitter_url = models.URLField(max_length=500, blank=True, default="")
    linkedin_url = models.URLField(max_length=500, blank=True, default="")
    github_url = models.URLField(max_length=500, blank=True, default="")

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    def __str__(self):
        return f"UserProfile({self.user.username})"

    def _convert_to_webp(self, image_field):
        """Helper method to convert an ImageField to WebP format."""
        if image_field and not image_field.name.lower().endswith(".webp"):
            import os
            from io import BytesIO

            from django.core.files.base import ContentFile
            from PIL import Image

            img = Image.open(image_field)

            if img.mode != "RGBA" and img.mode != "RGB":
                img = img.convert("RGBA")

            output = BytesIO()
            img.save(output, format="WEBP", quality=85)
            output.seek(0)

            base_name = os.path.splitext(os.path.basename(image_field.name))[0]
            new_filename = f"{base_name}.webp"

            image_field.save(new_filename, ContentFile(output.read()), save=False)

    def save(self, *args, **kwargs):
        self._convert_to_webp(self.avatar)
        self._convert_to_webp(self.cover_image)
        super().save(*args, **kwargs)
