from rest_framework import permissions

from apps.rbac.permissions import HasRole


class IsAdminRole(permissions.BasePermission):
    """
    Allows access only to admin users.
    Admins are defined as superusers, staff users, or users in the 'Admin' group.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        return HasRole("Administrator").has_permission(request, view)


class IsModeratorRole(permissions.BasePermission):
    """
    Allows access only to moderator users.
    Moderators are defined as users in the 'Moderator' group.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return HasRole("Moderator").has_permission(request, view)


class IsAdminOrModeratorRole(permissions.BasePermission):
    """
    Allows access to both admin and moderator users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        return HasRole("Administrator").has_permission(request, view) or HasRole(
            "Moderator"
        ).has_permission(request, view)
