from rest_framework import permissions

from .models import UserRole


class HasPermission(permissions.BasePermission):
    def __init__(self, required_permission):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Check if user has any role that grants this permission
        user_roles = UserRole.objects.filter(user=request.user).select_related("role")
        for user_role in user_roles:
            if user_role.role.permissions.filter(
                slug=self.required_permission
            ).exists():
                return True

        return False


class HasRole(permissions.BasePermission):
    def __init__(self, required_role):
        self.required_role = required_role

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        return UserRole.objects.filter(
            user=request.user, role__name=self.required_role
        ).exists()
