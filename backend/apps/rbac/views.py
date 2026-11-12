from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.admin_events import (
    USER_ROLE_ASSIGNED,
    USER_ROLE_REVOKED,
    record_admin_event,
    target_type_for,
)
from apps.core.permissions import HasPermission, HasRole
from apps.organizations.models import Organization, OrganizationMembership

from .models import AuditLog, Permission, Role, UserRole
from .serializers import (
    AuditLogSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserRoleSerializer,
)

User = get_user_model()


def _get_user_organization_ids(user):
    """Return a set of organization IDs associated with the user."""
    if not user or not user.is_authenticated:
        return set()
    org_ids = set()

    profile = getattr(user, "user_profile", None) or getattr(user, "profile", None)
    if profile and getattr(profile, "organization_id", None):
        org_ids.add(profile.organization_id)

    try:
        user_org = getattr(user, "organization", None)
        if user_org and getattr(user_org, "id", None):
            org_ids.add(user_org.id)
    except (ObjectDoesNotExist, PermissionDenied):
        pass

    try:
        memberships = OrganizationMembership.objects.filter(user=user).values_list(
            "organization_id", flat=True
        )
        org_ids.update(memberships)
    except (ObjectDoesNotExist, PermissionDenied):
        pass

    roles_orgs = UserRole.objects.filter(
        user=user, organization__isnull=False
    ).values_list("organization_id", flat=True)
    org_ids.update(roles_orgs)

    return org_ids


def _user_belongs_to_org(user, organization_id):
    """Check if the user belongs to the specified organization."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if organization_id is None:
        return True
    try:
        org_id_int = int(organization_id)
    except (ValueError, TypeError):
        return False
    return org_id_int in _get_user_organization_ids(user)


def _get_user_primary_org_id(user):
    """Get the primary organization ID for a user if available."""
    org_ids = _get_user_organization_ids(user)
    if org_ids:
        return next(iter(org_ids))
    return None


class RoleListView(generics.ListAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class PermissionListView(generics.ListAPIView):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated]


class AssignRoleView(APIView):
    permission_classes = [
        permissions.IsAuthenticated,
        lambda: HasPermission("manage_roles"),
    ]

    def post(self, request):
        target_user_id = request.data.get("user_id")
        role_id = request.data.get("role_id")
        organization_id = request.data.get("organization_id", None)

        try:
            target_user = User.objects.get(id=target_user_id)
            role = Role.objects.get(id=role_id)
        except (User.DoesNotExist, Role.DoesNotExist):
            return Response(
                {"error": "User or Role not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if organization_id is not None:
            if not Organization.objects.filter(id=organization_id).exists():
                return Response(
                    {"error": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            organization_id = _get_user_primary_org_id(
                request.user
            ) or _get_user_primary_org_id(target_user)

        # Enforce multi-tenant organization boundaries for non-superusers
        if not request.user.is_superuser:
            if organization_id is not None:
                if not _user_belongs_to_org(request.user, organization_id):
                    return Response(
                        {
                            "error": "You do not have permission to manage roles in this organization"
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if not _user_belongs_to_org(target_user, organization_id):
                    return Response(
                        {"error": "Target user does not belong to this organization"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                admin_orgs = _get_user_organization_ids(request.user)
                target_orgs = _get_user_organization_ids(target_user)
                if (
                    admin_orgs
                    and target_orgs
                    and not admin_orgs.intersection(target_orgs)
                ):
                    return Response(
                        {"error": "Cross-organization role assignment is forbidden"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        user_role, created = UserRole.objects.get_or_create(
            user=target_user, role=role, organization_id=organization_id
        )

        if created:
            AuditLog.objects.create(
                actor=request.user,
                target_user=target_user,
                action="assign",
                role=role,
                organization_id=organization_id,
                details=f"Assigned role {role.name}",
            )
            record_admin_event(
                operation=USER_ROLE_ASSIGNED,
                action="created",
                target_type=target_type_for(target_user),
                target_id=target_user.pk,
                request=request,
                payload={
                    "role_id": role.pk,
                    "role_name": role.name,
                    "organization_id": organization_id,
                },
                summary=f"Assigned role {role.name} to user #{target_user.pk}",
            )
            return Response({"status": "Role assigned"}, status=status.HTTP_201_CREATED)
        return Response(
            {"status": "User already has this role"}, status=status.HTTP_200_OK
        )


class RevokeRoleView(APIView):
    permission_classes = [
        permissions.IsAuthenticated,
        lambda: HasPermission("manage_roles"),
    ]

    def post(self, request):
        target_user_id = request.data.get("user_id")
        role_id = request.data.get("role_id")
        organization_id = request.data.get("organization_id", None)

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if organization_id is not None:
            if not Organization.objects.filter(id=organization_id).exists():
                return Response(
                    {"error": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            organization_id = _get_user_primary_org_id(
                request.user
            ) or _get_user_primary_org_id(target_user)

        # Enforce multi-tenant organization boundaries for non-superusers
        if not request.user.is_superuser:
            if organization_id is not None:
                if not _user_belongs_to_org(request.user, organization_id):
                    return Response(
                        {
                            "error": "You do not have permission to manage roles in this organization"
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if not _user_belongs_to_org(target_user, organization_id):
                    return Response(
                        {"error": "Target user does not belong to this organization"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                admin_orgs = _get_user_organization_ids(request.user)
                target_orgs = _get_user_organization_ids(target_user)
                if (
                    admin_orgs
                    and target_orgs
                    and not admin_orgs.intersection(target_orgs)
                ):
                    return Response(
                        {"error": "Cross-organization role revocation is forbidden"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        try:
            user_role = UserRole.objects.get(
                user_id=target_user_id, role_id=role_id, organization_id=organization_id
            )
            role = user_role.role
            user_role.delete()

            AuditLog.objects.create(
                actor=request.user,
                target_user=target_user,
                action="revoke",
                role=role,
                organization_id=organization_id,
                details=f"Revoked role {role.name}",
            )
            record_admin_event(
                operation=USER_ROLE_REVOKED,
                action="deleted",
                target_type=target_type_for(target_user),
                target_id=target_user.pk,
                request=request,
                payload={
                    "role_id": role.pk,
                    "role_name": role.name,
                    "organization_id": organization_id,
                },
                summary=f"Revoked role {role.name} from user #{target_user.pk}",
            )
            return Response({"status": "Role revoked"}, status=status.HTTP_200_OK)
        except UserRole.DoesNotExist:
            return Response(
                {"error": "Role assignment not found"}, status=status.HTTP_404_NOT_FOUND
            )


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        lambda: HasPermission("view_audit_logs"),
    ]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return AuditLog.objects.all()

        organization_ids = UserRole.objects.filter(
            user=self.request.user,
            role__permissions__slug="view_audit_logs",
            organization__isnull=False,
        ).values("organization_id")
        return AuditLog.objects.filter(organization_id__in=organization_ids)
