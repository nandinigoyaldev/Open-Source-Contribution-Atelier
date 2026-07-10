import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import UserProfile


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
            if hasattr(instance, "user_profile"):
                profile = instance.user_profile
            else:
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
            instance.user_profile = profile

        return instance


class UserListSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    twitter_url = serializers.SerializerMethodField()
    linkedin_url = serializers.SerializerMethodField()
    github_url = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    receive_weekly_digest = serializers.SerializerMethodField()

    class Meta:
        model = User
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
            "bio",
            "receive_weekly_digest",
        )

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

    def get_bio(self, obj):
        if hasattr(obj, "user_profile"):
            return obj.user_profile.bio
        return ""

    def get_receive_weekly_digest(self, obj):
        if hasattr(obj, "user_profile"):
            return obj.user_profile.receive_weekly_digest
        return True


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login with either username or email in the username field."""

    def validate(self, attrs):
        username_key = self.username_field
        identifier = attrs.get(username_key, "")

        if isinstance(identifier, str) and "@" in identifier:
            user = User.objects.filter(email__iexact=identifier.strip()).first()
            if user:
                attrs = {**attrs, username_key: user.username}

        result = super().validate(attrs)

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

        return result


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


class AvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.ImageField(
        max_length=255, allow_empty_file=False, use_url=True
    )

    def validate_avatar(self, value):
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image size must be under 5MB")

        # Check file extension
        allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        ext = value.name.split(".")[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"File type not supported. Use: {', '.join(allowed_extensions)}"
            )

        return value


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ["avatar", "avatar_url"]

    def get_avatar_url(self, obj):
        if obj.avatar:
            return obj.avatar.url
        return None


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
