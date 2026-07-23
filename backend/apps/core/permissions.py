"""
Permissions for cross-tenant data isolation.

:class:`IsTenantMember` enforces object-level tenant membership. When
combined with :class:`apps.core.mixins.OrganizationScopedQuerySetMixin`
the typical cross-tenant access pattern is:

    * LIST  -> empty queryset (no rows visible) -> 200 with ``[]``
    * DETAIL -> object not in scoped queryset -> 404 (secure default)

For endpoints where you want an explicit **403 Forbidden** instead of
404 (e.g. to surface the policy violation in audit logs), add
``IsTenantMember`` to ``permission_classes`` AND call
``self.check_object_permissions(request, obj)`` in the view. This
permission inspects the object's tenant discriminator and returns
``False`` (→ 403) when it differs from the request's tenant.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


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

    # -- helpers -----------------------------------------------------------

    def _object_org_id(self, obj):
        # 1. Explicit organization FK.
        org = getattr(obj, "organization_id", None)
        if org is not None:
            return org
        org = getattr(obj, "organization", None)
        if org is not None:
            return getattr(org, "id", None) or getattr(org, "pk", None)

        # 2. Derived from owning user's profile.
        user = getattr(obj, "user", None)
        if user is not None:
            profile = getattr(user, "user_profile", None)
            if profile is not None:
                return getattr(profile, "organization_id", None)

        return None


class IsTenantMemberOrReadOnly(IsTenantMember):
    """Like :class:`IsTenantMember` but allows safe methods to any tenant member."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return super().has_object_permission(request, view, obj)
        # Unsafe methods additionally require the object to be in the
        # current tenant (same check; expressed separately for clarity
        # and future extension, e.g. role checks).
        return super().has_object_permission(request, view, obj)
