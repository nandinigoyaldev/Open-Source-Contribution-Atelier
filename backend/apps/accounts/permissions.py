from rest_framework import permissions


class IsAdminRole(permissions.BasePermission):
    """
    Allows access only to admin users.
    Admins are defined as superusers, staff users, or users in the 'Admin' group.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        return bool(
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name="Admin").exists()
        )


class IsModeratorRole(permissions.BasePermission):
    """
    Allows access only to moderator users.
    Moderators are defined as users in the 'Moderator' group.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        return bool(user.groups.filter(name="Moderator").exists())


class IsAdminOrModeratorRole(permissions.BasePermission):
    """
    Allows access to both admin and moderator users.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        return bool(
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name__in=["Admin", "Moderator"]).exists()
        )
