from typing import Any

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.feature_flags.models import FeatureFlag
from apps.feature_flags.serializers import (
    FeatureFlagAuditLogSerializer,
    FeatureFlagSerializer,
    FeatureFlagSummarySerializer,
)
from apps.feature_flags.services import (
    current_environment,
    evaluate_feature_flag,
    flag_snapshot,
    forget_flag_state,
    record_flag_change,
    remember_flag_state,
    rollback_feature_flag,
    set_kill_switch,
)

# Typed loosely because Pyright cannot follow atomic() without django-stubs.
atomic: Any = transaction.atomic


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """
    Admin-guarded API viewset for database-backed feature flags with audit logging,
    environment scoping, an emergency kill switch, dry-run evaluation, and
    one-action rollback.
    """

    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    # Flags carry targeting lists (user and organization ids), so reads are
    # admin-only too, not just writes.
    permission_classes = [permissions.IsAdminUser]

    def list(self, request, *args, **kwargs):
        # The admin page only needs scope and rollout impact, not who is targeted.
        flags = self.filter_queryset(self.get_queryset())
        return Response(FeatureFlagSummarySerializer(flags, many=True).data)

    def perform_create(self, serializer):
        reason = self.request.data.get("change_reason", "Initial flag creation")
        with atomic():
            flag = serializer.save()
            record_flag_change(
                flag=flag,
                actor=self.request.user,
                action="created",
                scope="global",
                old_values={},
                new_values=flag_snapshot(flag, include_name=True),
                reason=reason,
            )
        remember_flag_state(flag)

    def perform_update(self, serializer):
        old_values = flag_snapshot(serializer.instance, include_name=True)
        reason = self.request.data.get("change_reason", "Configuration update")
        with atomic():
            updated_flag = serializer.save()
            if updated_flag.environments:
                scope = "environment"
            elif updated_flag.flag_type in ("organization", "percentage"):
                scope = updated_flag.flag_type
            else:
                scope = "global"
            record_flag_change(
                flag=updated_flag,
                actor=self.request.user,
                action="updated",
                scope=scope,
                old_values=old_values,
                new_values=flag_snapshot(updated_flag, include_name=True),
                reason=reason,
            )
        if old_values["name"] != updated_flag.name:
            forget_flag_state(old_values["name"])
        remember_flag_state(updated_flag)

    def perform_destroy(self, instance):
        name = instance.name
        super().perform_destroy(instance)
        forget_flag_state(name)

    @action(detail=True, methods=["get"], url_path="audit-logs")
    def audit_logs(self, request, pk=None):
        flag = self.get_object()
        logs = flag.audit_logs.select_related("actor").order_by("-timestamp")
        serializer = FeatureFlagAuditLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="kill-switch")
    def kill_switch(self, request, pk=None):
        """Emergency disable (``{"engaged": true}``) or release it again."""
        flag = self.get_object()
        engaged = request.data.get("engaged", True)
        if isinstance(engaged, str):
            engaged = engaged.strip().lower() in ("1", "true", "yes", "on")
        reason = str(request.data.get("reason", "") or "").strip()
        audit = set_kill_switch(
            flag, engaged=bool(engaged), actor=request.user, reason=reason
        )
        flag.refresh_from_db()
        return Response(
            {
                "status": "unchanged" if audit is None else "updated",
                # Same shape as the list rows the admin page renders.
                "flag": FeatureFlagSummarySerializer(flag).data,
                "audit_log": (
                    FeatureFlagAuditLogSerializer(audit).data if audit else None
                ),
            },
            status=status.HTTP_200_OK,
        )

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
        environment = request.data.get("environment") or current_environment()

        is_enabled, reason = evaluate_feature_flag(
            flag, user=target_user, organization=target_org, environment=environment
        )

        return Response(
            {
                "flag_name": flag.name,
                "is_enabled": is_enabled,
                "reason": reason,
                "evaluated_context": {
                    "user": target_user,
                    "organization": target_org,
                    "environment": environment,
                },
                "flag_state": {
                    "is_active": flag.is_active,
                    "kill_switch": flag.kill_switch,
                    "flag_type": flag.flag_type,
                    "rollout_percentage": flag.rollout_percentage,
                    "environments": flag.environments,
                    "default_value": flag.default_value,
                },
            },
            status=status.HTTP_200_OK,
        )
