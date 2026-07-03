from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from .models import Permission, Role, UserRole, AuditLog
from .serializers import (
    PermissionSerializer,
    RoleSerializer,
    UserRoleSerializer,
    AuditLogSerializer,
)
from .permissions import HasRole, HasPermission

from .models import AuditLog, Permission, Role, UserRole
from .permissions import HasPermission, HasRole
from .serializers import (
    AuditLogSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserRoleSerializer,
)

main


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
            user_role = UserRole.objects.get(
                user_id=target_user_id, role_id=role_id, organization_id=organization_id
            )
            role = user_role.role
            target_user = user_role.user
            user_role.delete()

            AuditLog.objects.create(
                actor=request.user,
                target_user=target_user,
                action="revoke",
                role=role,
                organization_id=organization_id,
                details=f"Revoked role {role.name}",
            )
            return Response({"status": "Role revoked"}, status=status.HTTP_200_OK)
        except UserRole.DoesNotExist:
            return Response(
                {"error": "Role assignment not found"}, status=status.HTTP_404_NOT_FOUND
            )


class AuditLogListView(generics.ListAPIView):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        lambda: HasPermission("view_audit_logs"),
    ]
