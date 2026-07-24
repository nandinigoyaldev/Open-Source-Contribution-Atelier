from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Organization, OrganizationAuditLog, OrganizationMembership
from .permissions import IsMembershipOrgAdminOrOwner, IsOrganizationAdminOrOwner
from .serializers import OrganizationMembershipSerializer, OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get_queryset(self):
        # Only return organizations the requesting user actually belongs
        # to — previously this returned Organization.objects.all() to any
        # authenticated user regardless of membership.
        return Organization.objects.filter(
            memberships__user=self.request.user
        ).distinct()

    def perform_create(self, serializer):
        organization = serializer.save()
        OrganizationMembership.objects.create(
            organization=organization,
            user=self.request.user,
            role=OrganizationMembership.ROLE_OWNER,
        )
        OrganizationAuditLog.objects.create(
            organization_id=organization.id,
            organization_name=organization.name,
            actor=self.request.user,
            action=OrganizationAuditLog.ACTION_CREATED,
            changes={
                "name": organization.name,
                "description": organization.description,
            },
        )

    def perform_update(self, serializer):
        before = {
            "name": serializer.instance.name,
            "description": serializer.instance.description,
        }
        organization = serializer.save()
        after = {"name": organization.name, "description": organization.description}
        OrganizationAuditLog.objects.create(
            organization_id=organization.id,
            organization_name=organization.name,
            actor=self.request.user,
            action=OrganizationAuditLog.ACTION_UPDATED,
            changes={"before": before, "after": after},
        )

    def perform_destroy(self, instance):
        # Prevent deleting an organization that would leave it with zero
        # owners accidentally through some future bulk-role-change flow;
        # for a direct delete by an owner/admin this is just a safety net
        # and an audit record.
        OrganizationAuditLog.objects.create(
            organization_id=instance.id,
            organization_name=instance.name,
            actor=self.request.user,
            action=OrganizationAuditLog.ACTION_DELETED,
            changes={"name": instance.name},
        )
        # Cascade delete: Organization -> OrganizationMembership rows are
        # removed automatically via on_delete=CASCADE on the FK.
        instance.delete()


class OrganizationMembershipViewSet(viewsets.ModelViewSet):
    """
    Nested under /api/organizations/<organization_pk>/members/.
    Lets owners/admins add, remove, and change the role of members.
    """

    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated, IsMembershipOrgAdminOrOwner]

    def get_queryset(self):
        return OrganizationMembership.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).select_related("user")

    def perform_create(self, serializer):
        organization_id = self.kwargs["organization_pk"]
        membership = serializer.save(organization_id=organization_id)
        OrganizationAuditLog.objects.create(
            organization_id=organization_id,
            organization_name=membership.organization.name,
            actor=self.request.user,
            action=OrganizationAuditLog.ACTION_MEMBER_ADDED,
            changes={"user": membership.user_id, "role": membership.role},
        )

    def perform_update(self, serializer):
        before_role = serializer.instance.role
        membership = serializer.save()
        OrganizationAuditLog.objects.create(
            organization_id=membership.organization_id,
            organization_name=membership.organization.name,
            actor=self.request.user,
            action=OrganizationAuditLog.ACTION_MEMBER_ROLE_CHANGED,
            changes={
                "user": membership.user_id,
                "before_role": before_role,
                "after_role": membership.role,
            },
        )

    def perform_destroy(self, instance):
        # Don't allow removing the last owner of an organization — that
        # would leave it ownerless.
        if instance.role == OrganizationMembership.ROLE_OWNER:
            remaining_owners = (
                OrganizationMembership.objects.filter(
                    organization=instance.organization,
                    role=OrganizationMembership.ROLE_OWNER,
                )
                .exclude(pk=instance.pk)
                .count()
            )
            if remaining_owners == 0:
                raise PermissionDenied(
                    "Cannot remove the last owner of an organization."
                )

        OrganizationAuditLog.objects.create(
            organization_id=instance.organization_id,
            organization_name=instance.organization.name,
            actor=self.request.user,
            action=OrganizationAuditLog.ACTION_MEMBER_REMOVED,
            changes={"user": instance.user_id, "role": instance.role},
        )
        instance.delete()
