import re
from datetime import timedelta

from django.contrib.auth.models import User
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
    timezone = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ("email", "password", "avatar", "timezone")
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
        tz = validated_data.pop("timezone", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
            if hasattr(instance, "profile"):
                instance.profile.last_password_change = timezone.now()
                instance.profile.save(update_fields=["last_password_change"])
        instance.save()

        if avatar is not None or tz is not None:
            from apps.accounts.models import UserProfile

            profile, _ = UserProfile.objects.get_or_create(user=instance)
            if avatar is not None:
                profile.avatar = avatar
            if tz is not None:
                profile.timezone = tz
            profile.save()

        return instance


class UserListSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff", "avatar_url", "timezone")

    def get_avatar_url(self, obj):
        if hasattr(obj, "profile") and obj.profile.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile.avatar.url)
            return obj.profile.avatar.url
        return None

    def get_timezone(self, obj):
        if hasattr(obj, "profile"):
            return obj.profile.timezone
        return "UTC"


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

        if hasattr(self.user, "profile") and self.user.profile.last_password_change:
            if timezone.now() > self.user.profile.last_password_change + timedelta(
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
