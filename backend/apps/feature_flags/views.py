from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.feature_flags.models import FeatureFlag, FeatureFlagAuditLog
from apps.feature_flags.serializers import (
    FeatureFlagAuditLogSerializer,
    FeatureFlagSerializer,
)
from apps.feature_flags.services import (
    evaluate_feature_flag,
    record_flag_change,
    rollback_feature_flag,
)


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """
    Admin-guarded API viewset for database-backed feature flags with audit logging,
    rollout safeguards, dry-run evaluation, and one-action rollback.
    """

    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer

    def get_permissions(self):
        # Read-only operations require authenticated users; mutations require Admin/Staff
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    def perform_create(self, serializer):
        reason = self.request.data.get("change_reason", "Initial flag creation")
        flag = serializer.save()
        new_values = {
            "name": flag.name,
            "is_active": flag.is_active,
            "flag_type": flag.flag_type,
            "rollout_percentage": flag.rollout_percentage,
            "target_organizations": flag.target_organizations,
            "target_users": flag.target_users,
            "default_value": flag.default_value,
        }
        record_flag_change(
            flag=flag,
            actor=self.request.user,
            action="created",
            scope="global",
            old_values={},
            new_values=new_values,
            reason=reason,
        )

    def perform_update(self, serializer):
        flag = self.get_object()
        old_values = {
            "name": flag.name,
            "is_active": flag.is_active,
            "flag_type": flag.flag_type,
            "rollout_percentage": flag.rollout_percentage,
            "target_organizations": flag.target_organizations,
            "target_users": flag.target_users,
            "default_value": flag.default_value,
        }
        reason = self.request.data.get("change_reason", "Configuration update")
        updated_flag = serializer.save()
        new_values = {
            "name": updated_flag.name,
            "is_active": updated_flag.is_active,
            "flag_type": updated_flag.flag_type,
            "rollout_percentage": updated_flag.rollout_percentage,
            "target_organizations": updated_flag.target_organizations,
            "target_users": updated_flag.target_users,
            "default_value": updated_flag.default_value,
        }
        scope = (
            "organization"
            if updated_flag.flag_type == "organization"
            else ("percentage" if updated_flag.flag_type == "percentage" else "global")
        )
        record_flag_change(
            flag=updated_flag,
            actor=self.request.user,
            action="updated",
            scope=scope,
            old_values=old_values,
            new_values=new_values,
            reason=reason,
        )

    @action(detail=True, methods=["get"], url_path="audit-logs")
    def audit_logs(self, request, pk=None):
        flag = self.get_object()
        logs = flag.audit_logs.all().order_by("-timestamp")
        serializer = FeatureFlagAuditLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, pk=None):
        flag = self.get_object()
        reason = request.data.get("reason", "Admin requested rollback")
        target_audit_id = request.data.get("target_audit_id")
        try:
            audit = rollback_feature_flag(
                flag,
                actor=request.user,
                reason=reason,
                target_audit_id=target_audit_id,
            )
            return Response(
                {
                    "status": "rolled_back",
                    "flag": FeatureFlagSerializer(flag).data,
                    "audit_log": FeatureFlagAuditLogSerializer(audit).data,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="dry-run")
    def dry_run(self, request):
        flag_name = request.data.get("flag_name") or request.data.get("name")
        if not flag_name:
            return Response(
                {"error": "flag_name is required for dry-run evaluation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        flag = FeatureFlag.objects.filter(name=flag_name).first()
        if not flag:
            return Response(
                {
                    "flag_name": flag_name,
                    "is_enabled": False,
                    "reason": "flag_not_found",
                },
                status=status.HTTP_200_OK,
            )

        target_user = request.data.get("user") or request.data.get("user_id")
        target_org = request.data.get("organization") or request.data.get("org")

        is_enabled, reason = evaluate_feature_flag(
            flag, user=target_user, organization=target_org
        )

        return Response(
            {
                "flag_name": flag.name,
                "is_enabled": is_enabled,
                "reason": reason,
                "evaluated_context": {
                    "user": target_user,
                    "organization": target_org,
                },
                "flag_state": {
                    "is_active": flag.is_active,
                    "flag_type": flag.flag_type,
                    "rollout_percentage": flag.rollout_percentage,
                    "default_value": flag.default_value,
                },
            },
            status=status.HTTP_200_OK,
        )
