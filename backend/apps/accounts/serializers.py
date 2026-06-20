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

    def validate_password(self, value):
        return validate_strong_password(value)

    def create(self, validated_data):
        if "email" in validated_data:
            validated_data["email"] = validated_data["email"].lower()
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
