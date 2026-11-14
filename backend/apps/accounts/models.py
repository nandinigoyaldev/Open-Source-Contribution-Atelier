import uuid
from typing import Optional

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.content.models import Lesson
from apps.core.fields import EncryptedCharField
from apps.core.models import AuditableModel


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

    Only a keyed hash of the token is stored. The raw value is generated in save()
    and stays on that one instance as `token`, long enough to put it in the email.
    It cannot be read back from the database.
    """

    # Salting with the purpose ties a hash to this one action: the same value
    # hashed for anything else will not match.
    HASH_SALT = "apps.accounts.PasswordResetToken"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    # Raw token. Not a database field, and None on any row loaded from the database.
    token: Optional[uuid.UUID] = None

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PasswordResetToken(user={self.user.username}, used={self.is_used})"

    @classmethod
    def hash_token(cls, value) -> str:
        """Hash a raw token. Raises ValueError when `value` is not a UUID."""
        return salted_hmac(
            cls.HASH_SALT, str(uuid.UUID(str(value))), algorithm="sha256"
        ).hexdigest()

    def save(self, *args, **kwargs):
        if not self.token_hash:
            self.token = uuid.uuid4()
            self.token_hash = self.hash_token(self.token)
        super().save(*args, **kwargs)

    def is_expired(self) -> bool:
        """Return True if the token is older than PASSWORD_RESET_TIMEOUT_SECONDS (15 minutes)."""
        from datetime import timedelta

        from django.utils import timezone

        timeout_seconds = getattr(settings, "PASSWORD_RESET_TIMEOUT_SECONDS", 900)
        return timezone.now() > self.created_at + timedelta(seconds=timeout_seconds)


class OTPToken(models.Model):
    """
    Secure OTP token sent to a user's email for verification.

    Tokens expire after settings.OTP_TIMEOUT_MINUTES (default 10).
    Once used, `is_used` is set to True and the token cannot be reused.
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

    def is_expired(self) -> bool:
        """Return True if the token is older than OTP_TIMEOUT_MINUTES (default 10)."""
        from datetime import timedelta

        from django.utils import timezone

        timeout = getattr(settings, "OTP_TIMEOUT_MINUTES", 10)
        return timezone.now() > self.created_at + timedelta(minutes=timeout)


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
        """Return True if the token is older than MAGIC_LINK_TIMEOUT_MINUTES (default 15)."""
        from datetime import timedelta

        timeout = getattr(settings, "MAGIC_LINK_TIMEOUT_MINUTES", 15)
        return timezone.now() > self.created_at + timedelta(minutes=timeout)


def get_timezone_choices():
    from zoneinfo import available_timezones

    return sorted((tz, tz) for tz in available_timezones())


class UserProfile(AuditableModel):
    """
    Standard user profile linking to the main User model.
    Stores the user's avatar image and JWT token version.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_profile",
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        max_length=255,
    )
    cover_image = models.ImageField(upload_to="covers/", null=True, blank=True)
    last_password_change = models.DateTimeField(
        auto_now_add=True, null=True, blank=True
    )
    timezone = models.CharField(
        max_length=64,
        choices=get_timezone_choices(),
        default="UTC",
    )
    twitter_url = models.URLField(max_length=500, blank=True, default="")
    linkedin_url = models.URLField(max_length=500, blank=True, default="")
    github_url = models.URLField(max_length=500, blank=True, default="")
    bio = models.TextField(max_length=500, blank=True, default="")
    receive_weekly_digest = models.BooleanField(
        default=True, help_text="Receive automated weekly progress digest emails"
    )
    weekend_learning_enabled = models.BooleanField(
        default=False,
        help_text="Whether weekend learning activity is part of the user's normal schedule",
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    github_access_token = EncryptedCharField(max_length=255, blank=True, default="")
    github_access_token_hash = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )

    google_oauth_token = EncryptedCharField(max_length=255, blank=True, default="")
    google_oauth_token_hash = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )

    # ============================================================
    # ✅ ADDED: JWT Token Version for Invalidation
    # ============================================================
    jwt_token_version = models.IntegerField(
        default=1,
        help_text="Incremented on password change to invalidate existing JWT tokens",
    )

    class Meta:
        db_table = "accounts_userprofile"

    def audit_snapshot_fields(self) -> list:
        exclude = {
            "github_access_token",
            "github_access_token_hash",
            "google_oauth_token",
            "google_oauth_token_hash",
        }
        return [f.name for f in self._meta.fields if f.name not in exclude]

    def __str__(self):
        return f"UserProfile({self.user.username})"

    def __repr__(self):
        return f"<UserProfile: {self.user.username}>"

    @property
    def local_today(self):
        """
        Return the current date in the user's configured timezone.
        Falls back to UTC if the timezone is invalid or not set.
        """
        import zoneinfo

        from django.utils import timezone

        tz_name = self.timezone or "UTC"
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = zoneinfo.ZoneInfo("UTC")

        return timezone.now().astimezone(user_tz).date()

    def increment_jwt_version(self):
        """
        Increment JWT token version to invalidate all existing tokens.
        Called when user changes password.
        """
        self.jwt_token_version += 1
        self.last_password_change = timezone.now()
        self.save(update_fields=["jwt_token_version", "last_password_change"])

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
        import hashlib

        if self.github_access_token:
            self.github_access_token_hash = hashlib.sha256(
                self.github_access_token.encode("utf-8")
            ).hexdigest()
        else:
            self.github_access_token_hash = ""

        if self.google_oauth_token:
            self.google_oauth_token_hash = hashlib.sha256(
                self.google_oauth_token.encode("utf-8")
            ).hexdigest()
        else:
            self.google_oauth_token_hash = ""

        self._convert_to_webp(self.avatar)
        self._convert_to_webp(self.cover_image)
        super().save(*args, **kwargs)


class UserSession(models.Model):
    """
    Tracks active user sessions to enforce concurrent limits and allow remote revocation.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    device_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity"]

    def __str__(self):
        return f"Session {self.session_id} for {self.user.username}"

    def save(self, *args, **kwargs):
        max_sessions = getattr(settings, "MAX_SESSIONS_PER_USER", 5)

        with transaction.atomic():
            # Lock all existing sessions for this user.  The lock
            # serialises concurrent save() calls for the same user:
            # whichever transaction acquires the lock first will
            # complete its save + eviction before the next one
            # proceeds, eliminating the TOCTOU race condition.
            locked_qs = (
                UserSession.objects.select_for_update()
                .filter(user=self.user)
                .order_by("-last_activity")
            )

            # Materialise the locked queryset so the DB lock is held
            # for the duration of the transaction.
            existing_ids = list(locked_qs.values_list("pk", flat=True))

            # Persist (insert or update) the current session *inside*
            # the same atomic block so it is covered by the lock.
            super().save(*args, **kwargs)

            # Re-evaluate sessions now that the current one is saved.
            all_sessions = UserSession.objects.filter(user=self.user).order_by(
                "-last_activity"
            )

            if all_sessions.count() > max_sessions:
                ids_to_keep = list(
                    all_sessions.values_list("pk", flat=True)[:max_sessions]
                )
                UserSession.objects.filter(user=self.user).exclude(
                    pk__in=ids_to_keep
                ).delete()


class GitCredential(models.Model):
    """
    Stores encrypted Git credentials.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="git_credentials",
    )
    provider = models.CharField(max_length=50, default="github")
    token = EncryptedCharField(max_length=255, blank=True, default="")
    token_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    password = EncryptedCharField(max_length=255, blank=True, default="")
    password_hash = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        import hashlib

        if self.token:
            self.token_hash = hashlib.sha256(self.token.encode("utf-8")).hexdigest()
        else:
            self.token_hash = ""

        if self.password:
            self.password_hash = hashlib.sha256(
                self.password.encode("utf-8")
            ).hexdigest()
        else:
            self.password_hash = ""

        super().save(*args, **kwargs)

    def __str__(self):
        return f"GitCredential({self.user.username}, {self.provider})"

    def __repr__(self):
        return f"<GitCredential: {self.user.username}, {self.provider}>"


class TOTPDevice(models.Model):
    """
    Optional TOTP Two-Factor Authentication Device for user accounts.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="totp_device",
    )
    secret = EncryptedCharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list)  # Hashed SHA-256 backup codes
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_totpdevice"

    def __str__(self):
        return f"TOTPDevice({self.user.username}, enabled={self.is_enabled})"


class WebAuthnCredential(models.Model):
    """
    Stores WebAuthn (FIDO2) passkey credentials for a user.

    Each credential is linked to the user who registered it and stores
    the credential ID, public key, and sign count for replay-attack detection.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webauthn_credentials",
    )
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.BigIntegerField(default=0)
    nickname = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_webauthncredential"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"WebAuthnCredential(user={self.user.username}, nickname={self.nickname})"
        )


class AccountDeletionRequest(models.Model):
    """
    Tracks account deletion requests, grace periods, and outcomes.
    """

    STATUS_PENDING = "pending"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_deletion_requests",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "accounts_accountdeletionrequest"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"AccountDeletionRequest(user={self.user_id}, status={self.status})"
