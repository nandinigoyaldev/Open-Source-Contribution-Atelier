"""
Centralized reusable permissions for Django REST Framework (DRF).

This module contains:
- Cross-tenant isolation permissions (:class:`IsTenantMember`, :class:`IsTenantMemberOrReadOnly`)
- Common staff and access permissions (:class:`IsStaffMember`, :class:`IsAdminOrOwner`, :class:`HasValidApiKey`, :class:`IsMentor`, :class:`IsModeratorOrAdmin`)
- Lesson prerequisite permissions (:class:`IsLessonUnlocked`)
- Account role permissions (:class:`IsAdminRole`, :class:`IsModeratorRole`, :class:`IsAdminOrModeratorRole`)
- Organization membership permissions (:class:`IsOrganizationMember`, :class:`IsOrganizationAdminOrOwner`, :class:`IsMembershipOrgAdminOrOwner`)
- RBAC permissions (:class:`HasPermission`, :class:`HasRole`, :class:`HasAnyRole`, :class:`HasAnyPermission`)
"""

from django.core.cache import cache
from django.db import models
from rest_framework.permissions import SAFE_METHODS, BasePermission

# -- Tenant Isolation Permissions ---------------------------------------------


class IsTenantMember(BasePermission):
    """
    Object-level permission: the object must belong to the current tenant.

    Works with any model that exposes either:
        * ``organization_id`` (a :class:`TenantAwareModel`), or
        * ``user.user_profile.organization_id`` (user-owned models).
    """

    message = "You do not have access to this resource in this organization."

    def has_permission(self, request, view):
        # For list/create we rely on the queryset mixin; only require auth.
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        from apps.core.tenant import get_current_tenant_id

        current_org = get_current_tenant_id()
        if current_org is None:
            return False

        obj_org = self._object_org_id(obj)
        if obj_org is None:
            # Object has no tenant discriminator; deny by default.
            return False
        return obj_org == current_org

    def _object_org_id(self, obj):
        org = getattr(obj, "organization_id", None)
        if org is not None:
            return org
        org = getattr(obj, "organization", None)
        if org is not None:
            return getattr(org, "id", None) or getattr(org, "pk", None)

        user = getattr(obj, "user", None)
        if user is not None:
            profile = getattr(user, "user_profile", None)
            if profile is not None:
                return getattr(profile, "organization_id", None)

        return None


class IsTenantMemberOrReadOnly(IsTenantMember):
    """
    Like :class:`IsTenantMember` but allows safe methods (GET/HEAD/OPTIONS)
    to any authenticated tenant member.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return super().has_object_permission(request, view, obj)


# -- Staff & Generic Permission Classes ----------------------------------------


class IsStaffMember(BasePermission):
    """
    Allows access only to staff or superuser members.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsAdminOrOwner(BasePermission):
    """
    Allows access to staff/superuser members or the owner of the object.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        owner = (
            getattr(obj, "user", None)
            or getattr(obj, "actor", None)
            or getattr(obj, "owner", None)
        )
        return owner == request.user


class HasValidApiKey(BasePermission):
    """
    Allows access if a valid API key header (X-API-Key or HTTP_X_API_KEY) is present.
    """

    def has_permission(self, request, view):
        api_key = request.META.get("HTTP_X_API_KEY") or request.headers.get("X-API-Key")
        if not api_key:
            return False

        from django.conf import settings

        valid_keys = getattr(settings, "API_KEYS", None)
        if valid_keys is not None:
            return api_key in valid_keys
        return True


class IsMentor(BasePermission):
    """
    Allows access to designated mentors.
    """

    message = "You must be a designated mentor to access this resource."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and hasattr(request.user, "mentor_profile"))


class IsModeratorOrAdmin(BasePermission):
    """
    Allows access to staff members, superusers, or moderators.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


# -- Content / Lesson Permissions ---------------------------------------------


class IsLessonUnlocked(BasePermission):
    """
    Check if user has completed prerequisites for a lesson.
    """

    def has_permission(self, request, view):
        lesson_slug = view.kwargs.get("slug")
        user = request.user

        if not user or not user.is_authenticated:
            return False

        from apps.content.models import Lesson
        from apps.progress.models import LessonProgress

        try:
            lesson = Lesson.objects.get(slug=lesson_slug)
        except Lesson.DoesNotExist:
            return False

        if not hasattr(lesson, "prerequisites") or not lesson.prerequisites.exists():
            return True

        completed_lessons = LessonProgress.objects.filter(
            user=user, lesson__in=lesson.prerequisites.all(), completed=True
        ).values_list("lesson_id", flat=True)

        for prereq in lesson.prerequisites.all():
            if prereq.id not in completed_lessons:
                return False

        return True


# -- RBAC Permission Classes ---------------------------------------------------


class HasPermission(BasePermission):
    def __init__(self, required_permission=None):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not self.required_permission:
            return True

        from apps.rbac.models import UserRole

        user_roles = UserRole.objects.filter(user=request.user).select_related("role")
        organization = getattr(request.user, "organization", None)
        if organization is not None:
            user_roles = user_roles.filter(
                models.Q(organization=organization)
                | models.Q(organization__isnull=True)
            )
        for user_role in user_roles:
            if user_role.role.permissions.filter(
                slug=self.required_permission
            ).exists():
                return True

        return False


class HasRole(BasePermission):
    def __init__(self, required_role=None):
        self.required_role = required_role

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not self.required_role:
            return True

        from apps.rbac.models import UserRole

        return UserRole.objects.filter(
            user=request.user, role__name=self.required_role
        ).exists()


class HasAnyRole(BasePermission):
    def __init__(self, required_roles=None):
        self.required_roles = required_roles or []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not self.required_roles:
            return True

        from apps.rbac.models import UserRole

        return UserRole.objects.filter(
            user=request.user, role__name__in=self.required_roles
        ).exists()


class HasAnyPermission(BasePermission):
    def __init__(self, required_permissions=None):
        self.required_permissions = required_permissions or []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not self.required_permissions:
            return True

        from apps.rbac.models import UserRole

        user_roles = UserRole.objects.filter(user=request.user).select_related("role")
        for user_role in user_roles:
            if user_role.role.permissions.filter(
                slug__in=self.required_permissions
            ).exists():
                return True

        return False


# -- Accounts Role Permissions ------------------------------------------------


class IsAdminRole(BasePermission):
    """
    Allows access only to admin users.
    Admins are defined as superusers, staff users, or users in the 'Admin' group.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        return HasRole("Admin").has_permission(request, view)


class IsModeratorRole(BasePermission):
    """
    Allows access only to moderator users.
    Moderators are defined as users in the 'Moderator' group.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return HasRole("Moderator").has_permission(request, view)


class IsAdminOrModeratorRole(BasePermission):
    """
    Allows access to both admin and moderator users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        return HasRole("Admin").has_permission(request, view) or HasRole(
            "Moderator"
        ).has_permission(request, view)


# -- Organization Permissions ---------------------------------------------

ORG_CACHE_TTL = 300


def get_cached_organization_role(user_id, organization_id):
    """
    Returns the cached role of a user in an organization ('owner', 'admin', 'member', or None).
    Automatically invalidated upon membership create/update/delete via signals.
    """
    if not user_id or not organization_id:
        return None

    cache_key = f"org:user_role:{user_id}:{organization_id}"
    role = cache.get(cache_key)
    if role is not None:
        return role if role != "__NONE__" else None

    from apps.organizations.models import OrganizationMembership

    membership = (
        OrganizationMembership.objects.filter(
            organization_id=organization_id, user_id=user_id
        )
        .values_list("role", flat=True)
        .first()
    )

    cache.set(
        cache_key,
        membership if membership is not None else "__NONE__",
        ORG_CACHE_TTL,
    )
    return membership


class IsOrganizationMember(BasePermission):
    """
    Object-level permission: any membership role (owner/admin/member)
    grants read access to the organization.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_cached_organization_role(
            request.user.id, getattr(obj, "id", getattr(obj, "pk", None))
        )
        return role is not None


class IsOrganizationAdminOrOwner(BasePermission):
    """
    Object-level permission: safe methods (GET/HEAD/OPTIONS) require any
    membership; unsafe methods (PATCH/PUT/DELETE) require the requesting
    user to be an 'owner' or 'admin' member of the organization.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        org_id = getattr(obj, "id", getattr(obj, "pk", None))
        role = get_cached_organization_role(request.user.id, org_id)

        if role is None:
            return False

        if request.method in SAFE_METHODS:
            return True

        from apps.organizations.models import OrganizationMembership

        return role in (
            OrganizationMembership.ROLE_OWNER,
            OrganizationMembership.ROLE_ADMIN,
        )


class IsMembershipOrgAdminOrOwner(BasePermission):
    """
    Used by OrganizationMembershipViewSet. Grants access only if the
    requesting user is an owner/admin of the *parent* organization
    (identified by the `organization_pk` URL kwarg), regardless of
    which membership object is being read/written.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        organization_id = view.kwargs.get("organization_pk")
        if organization_id is None:
            return False

        role = get_cached_organization_role(request.user.id, organization_id)

        if role is None:
            return False

        if request.method in SAFE_METHODS:
            return True

        from apps.organizations.models import OrganizationMembership

        return role in (
            OrganizationMembership.ROLE_OWNER,
            OrganizationMembership.ROLE_ADMIN,
        )
