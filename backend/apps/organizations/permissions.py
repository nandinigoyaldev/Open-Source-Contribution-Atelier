from django.core.cache import cache
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import OrganizationMembership

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
        role = get_cached_organization_role(request.user.id, getattr(obj, "id", getattr(obj, "pk", None)))
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

        return role in (OrganizationMembership.ROLE_OWNER, OrganizationMembership.ROLE_ADMIN)


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

        return role in (OrganizationMembership.ROLE_OWNER, OrganizationMembership.ROLE_ADMIN)
