import re

from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


def validate_strong_password(value):
    if not re.search(r"\d", value):
        raise serializers.ValidationError(
            "Password must contain at least one number."
        )
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

    class Meta:
        model = User
        fields = ("email", "password")
        extra_kwargs = {
            "email": {"required": False},
        }

    def validate_password(self, value):
        return validate_strong_password(value)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff")


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login with either username or email in the username field."""

    def validate(self, attrs):
        username_key = self.username_field
        identifier = attrs.get(username_key, "")

        if isinstance(identifier, str) and "@" in identifier:
            user = User.objects.filter(email__iexact=identifier.strip()).first()
            if user:
                attrs = {**attrs, username_key: user.username}

        return super().validate(attrs)


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

