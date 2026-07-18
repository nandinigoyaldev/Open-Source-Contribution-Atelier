from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import OrganizationMembership


class IsOrganizationMember(BasePermission):
    """
    Object-level permission: any membership role (owner/admin/member)
    grants read access to the organization.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return OrganizationMembership.objects.filter(
            organization=obj, user=request.user
        ).exists()


class IsOrganizationAdminOrOwner(BasePermission):
    """
    Object-level permission: safe methods (GET/HEAD/OPTIONS) require any
    membership; unsafe methods (PATCH/PUT/DELETE) require the requesting
    user to be an 'owner' or 'admin' member of the organization.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        membership = OrganizationMembership.objects.filter(
            organization=obj, user=request.user
        ).first()

        if membership is None:
            return False

        if request.method in SAFE_METHODS:
            return True

        return membership.is_admin_or_owner


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

        membership = OrganizationMembership.objects.filter(
            organization_id=organization_id, user=request.user
        ).first()

        if membership is None:
            return False

        if request.method in SAFE_METHODS:
            return True

        return membership.is_admin_or_owner
