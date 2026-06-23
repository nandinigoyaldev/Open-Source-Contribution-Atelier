import uuid

from apps.content.models import Lesson
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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


class UserProfile(models.Model):
    """
    Standard user profile linking to the main User model.
    Stores the user's avatar image.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    last_password_change = models.DateTimeField(auto_now_add=True)

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    def __str__(self):
        return f"UserProfile({self.user.username})"

    def save(self, *args, **kwargs):
        if self.avatar and not self.avatar.name.lower().endswith('.webp'):
            img = Image.open(self.avatar)
            
            if img.mode != 'RGBA' and img.mode != 'RGB':
                img = img.convert('RGBA')
            
            output = BytesIO()
            img.save(output, format='WEBP', quality=85)
            output.seek(0)
            
            base_name = os.path.splitext(os.path.basename(self.avatar.name))[0]
            new_filename = f"{base_name}.webp"
            
            self.avatar.save(new_filename, ContentFile(output.read()), save=False)
            
        super().save(*args, **kwargs)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()
    else:
        UserProfile.objects.create(user=instance)


from django.contrib.auth import get_user_model

User = get_user_model()
User.add_to_class(
    "organization",
    property(lambda u: u.profile.organization if hasattr(u, "profile") else None),
)
