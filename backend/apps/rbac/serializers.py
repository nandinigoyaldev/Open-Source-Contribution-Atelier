from django.contrib.auth.models import User
from rest_framework import serializers

from .models import AuditLog, Permission, Role, UserRole




class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "slug", "description", "created_at"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "is_system_role",
            "permissions",
            "created_at",
        ]


class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserRole
        fields = ["id", "user", "username", "role", "organization", "created_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True)
    target_user_name = serializers.CharField(
        source="target_user.username", read_only=True
    )
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "target_user",
            "target_user_name",
            "action",
            "role",
            "role_name",
            "timestamp",
            "details",
        ]
