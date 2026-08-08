import re
from datetime import timedelta

from django.contrib.auth import get_user_model

User = get_user_model()
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


def validate_strong_password(value):
    if not re.search(r"\d", value):
        raise serializers.ValidationError("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
        raise serializers.ValidationError(
            "Password must contain at least one special character (!@#$%^&* etc)."
        )
    if not re.search(r"[A-Z]", value):
        raise serializers.ValidationError(
            "Password must contain at least one uppercase letter."
        )
    if not re.search(r"[a-z]", value):
        raise serializers.ValidationError(
            "Password must contain at least one lowercase letter."
        )
    return value


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def validate_username(self, value):
        """Reject duplicate usernames using a case-insensitive comparison."""
        normalized = value.strip()
        if User.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError("Username is already taken.")
        return normalized

    def validate_email(self, value):
        """Reject signup if the email address is already registered (case-insensitive)."""
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError(
                "An account with this email address already exists."
            )
        return normalized

    def validate_password(self, value):
        return validate_strong_password(value)

    def create(self, validated_data):
        # email is already normalized to lowercase by validate_email
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    avatar = serializers.ImageField(required=False)
    cover_image = serializers.ImageField(required=False)
    timezone = serializers.CharField(required=False)
    twitter_url = serializers.URLField(required=False, allow_blank=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)
    github_url = serializers.URLField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    receive_weekly_digest = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "avatar",
            "cover_image",
            "timezone",
            "twitter_url",
            "linkedin_url",
            "github_url",
            "bio",
            "receive_weekly_digest",
        )
        extra_kwargs = {
            "email": {"required": False},
        }

    def validate_password(self, value):
        return validate_strong_password(value)

    def validate_timezone(self, value):
        from zoneinfo import available_timezones

        if value not in available_timezones():
            raise serializers.ValidationError("Unknown timezone.")
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        avatar = validated_data.pop("avatar", None)
        cover_image = validated_data.pop("cover_image", None)
        tz = validated_data.pop("timezone", None)
        twitter_url = validated_data.pop("twitter_url", None)
        linkedin_url = validated_data.pop("linkedin_url", None)
        github_url = validated_data.pop("github_url", None)
        bio = validated_data.pop("bio", None)
        receive_weekly_digest = validated_data.pop("receive_weekly_digest", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
            if hasattr(instance, "user_profile"):
                instance.user_profile.last_password_change = timezone.now()
                instance.user_profile.save(update_fields=["last_password_change"])
        instance.save()

        if (
            avatar is not None
            or cover_image is not None
            or tz is not None
            or twitter_url is not None
            or linkedin_url is not None
            or github_url is not None
            or bio is not None
            or receive_weekly_digest is not None
        ):
            from apps.accounts.models import UserProfile

            profile, _ = UserProfile.objects.get_or_create(user=instance)
            if avatar is not None:
                profile.avatar = avatar
            if cover_image is not None:
                profile.cover_image = cover_image
            if tz is not None:
                profile.timezone = tz
            if twitter_url is not None:
                profile.twitter_url = twitter_url
            if linkedin_url is not None:
                profile.linkedin_url = linkedin_url
            if github_url is not None:
                profile.github_url = github_url
            if bio is not None:
                profile.bio = bio
            if receive_weekly_digest is not None:
                profile.receive_weekly_digest = receive_weekly_digest
            profile.save()

        return instance


class BulkUserListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        from apps.progress.services.milestone_track_service import MilestoneTrackService

        users = list(data)
        self.context["bulk_track_statuses"] = (
            MilestoneTrackService.get_users_active_track_statuses(users)
        )
        self.context["bulk_next_milestones"] = (
            MilestoneTrackService.get_users_next_milestones(users)
        )

        return super().to_representation(data)


class UserListSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    twitter_url = serializers.SerializerMethodField()
    linkedin_url = serializers.SerializerMethodField()
    github_url = serializers.SerializerMethodField()
    active_track_status = serializers.SerializerMethodField()
    next_milestone = serializers.SerializerMethodField()

    class Meta:
        model = User
        list_serializer_class = BulkUserListSerializer
        fields = (
            "id",
            "username",
            "email",
            "is_staff",
            "avatar_url",
            "cover_image_url",
            "timezone",
            "twitter_url",
            "linkedin_url",
            "github_url",
            "active_track_status",
            "next_milestone",
        )

    def get_active_track_status(self, obj):
        if "bulk_track_statuses" in self.context:
            return self.context["bulk_track_statuses"].get(obj.id)
        from apps.progress.services.milestone_track_service import MilestoneTrackService

        return MilestoneTrackService.get_user_active_track_status(obj)

    def get_next_milestone(self, obj):
        if "bulk_next_milestones" in self.context:
            return self.context["bulk_next_milestones"].get(obj.id)
        from apps.progress.services.milestone_track_service import MilestoneTrackService

        return MilestoneTrackService.get_user_next_milestone(obj)

    def get_avatar_url(self, obj):
        if hasattr(obj, "user_profile") and obj.user_profile.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.user_profile.avatar.url)
            return obj.user_profile.avatar.url
        return None

    def get_cover_image_url(self, obj):
        if hasattr(obj, "user_profile") and obj.user_profile.cover_image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.user_profile.cover_image.url)
            return obj.user_profile.cover_image.url
        return None

    def get_timezone(self, obj):
        if hasattr(obj, "user_profile"):
            return obj.user_profile.timezone
        return "UTC"

    def get_twitter_url(self, obj):
        if hasattr(obj, "user_profile") and obj.user_profile.twitter_url:
            return obj.user_profile.twitter_url
        return ""

    def get_linkedin_url(self, obj):
        if hasattr(obj, "user_profile") and obj.user_profile.linkedin_url:
            return obj.user_profile.linkedin_url
        return ""

    def get_github_url(self, obj):
        if hasattr(obj, "user_profile") and obj.user_profile.github_url:
            return obj.user_profile.github_url
        return ""


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login with either username or email in the username field, plus optional remember me lifetime and 2FA TOTP code validation."""

    remember = serializers.BooleanField(required=False, default=False)
    totp_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        username_key = self.username_field
        identifier = attrs.get(username_key, "")

        if isinstance(identifier, str) and "@" in identifier:
            user = User.objects.filter(email__iexact=identifier.strip()).first()
            if user:
                attrs = {**attrs, username_key: user.username}

        remember_me = self.initial_data.get("remember", False) or attrs.get("remember", False)

        result = super().validate(attrs)

        # Check optional 2FA TOTP enforcement
        if hasattr(self.user, "totp_device") and self.user.totp_device.is_enabled:
            totp_code = attrs.get("totp_code") or self.initial_data.get("totp_code")
            if not totp_code:
                raise AuthenticationFailed(
                    {
                        "requires_2fa": True,
                        "message": "Two-factor authentication code required.",
                    },
                    code="2fa_required",
                )

            from .totp import verify_and_consume_backup_code, verify_totp_code

            device = self.user.totp_device
            is_valid_totp = verify_totp_code(device.secret, totp_code)
            is_valid_backup = (
                verify_and_consume_backup_code(device, totp_code)
                if not is_valid_totp
                else False
            )

            if not is_valid_totp and not is_valid_backup:
                raise AuthenticationFailed(
                    {"totp_code": "Invalid 2FA authentication code or recovery code."},
                    code="invalid_2fa_code",
                )

            device.last_used_at = timezone.now()
            device.save(update_fields=["last_used_at"])

        if (
            hasattr(self.user, "user_profile")
            and self.user.user_profile.last_password_change
        ):
            if timezone.now() > self.user.user_profile.last_password_change + timedelta(
                days=90
            ):
                raise AuthenticationFailed(
                    "Password has expired. Please reset your password.",
                    code="password_expired",
                )

        request = self.context.get("request")
        ip_address = None
        user_agent = ""
        if request:
            ip_address = request.META.get("REMOTE_ADDR")
            user_agent = request.META.get("HTTP_USER_AGENT", "")

        from .models import UserSession

        session = UserSession.objects.create(
            user=self.user, ip_address=ip_address, user_agent=user_agent
        )

        refresh = self.get_token(self.user)
        if remember_me:
            refresh.set_exp(lifetime=timedelta(days=30))
            refresh.access_token.set_exp(lifetime=timedelta(days=7))

        refresh["session_id"] = str(session.session_id)

        access = refresh.access_token
        access["session_id"] = str(session.session_id)

        result["refresh"] = str(refresh)
        result["access"] = str(access)
        result["remember"] = bool(remember_me)

        return result


class TwoFactorVerifySerializer(serializers.Serializer):
    """Accept 6-digit TOTP verification code to confirm 2FA setup."""

    code = serializers.CharField(max_length=10, min_length=6)


class TwoFactorDisableSerializer(serializers.Serializer):
    """Accept user password to confirm disabling 2FA."""

    password = serializers.CharField(write_only=True)



# ─────────────────────────────────────────────────────────────────────────────
# Password Reset serializers
# ─────────────────────────────────────────────────────────────────────────────


class PasswordResetRequestSerializer(serializers.Serializer):
    """Accept an email address to trigger a password reset email."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Accept a reset token and the new password to complete the reset."""

    token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        return validate_strong_password(value)


# ─────────────────────────────────────────────────────────────────────────────
# OTP (Email Verification) serializers
# ─────────────────────────────────────────────────────────────────────────────


class OtpRequestSerializer(serializers.Serializer):
    """Accept an email address to trigger sending a new OTP verification code."""

    email = serializers.EmailField()


class OtpVerifySerializer(serializers.Serializer):
    """Accept email + OTP token to complete email verification."""

    email = serializers.EmailField()
    otp = serializers.UUIDField()


# ─────────────────────────────────────────────────────────────────────────────
# Magic Link serializers
# ─────────────────────────────────────────────────────────────────────────────


class MagicLinkRequestSerializer(serializers.Serializer):
    """Accept an email address to trigger a magic link login email."""

    email = serializers.EmailField()


class MagicLinkVerifySerializer(serializers.Serializer):
    """Accept a magic link token to verify and login the user."""

    token = serializers.UUIDField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        return validate_strong_password(value)


class AvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.ImageField(required=True)


class PasswordResetValidateTokenSerializer(serializers.Serializer):
    token = serializers.UUIDField(required=True)


from .models import UserSession


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = (
            "id",
            "session_id",
            "ip_address",
            "user_agent",
            "device_name",
            "created_at",
            "last_activity",
        )
        read_only_fields = fields
