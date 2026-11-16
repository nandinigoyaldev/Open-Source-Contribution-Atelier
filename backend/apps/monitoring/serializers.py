from django.utils import timezone
from rest_framework import serializers

from apps.audit.redaction import redact_string
from apps.monitoring.models import BackupVerification, TaskRun


class BackupVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupVerification
        fields = [
            "id",
            "backup_timestamp",
            "verification_timestamp",
            "size_bytes",
            "status",
            "logs",
        ]


class TaskRunSerializer(serializers.ModelSerializer):
    """
    ``args_summary`` is redacted when it is stored, and it and ``error_message`` go
    through ``redact_string`` again on the way out, so rows written before that
    redaction existed, or by another code path, cannot leak a credential.
    """

    queue_age_seconds = serializers.SerializerMethodField()

    class Meta:
        model = TaskRun
        fields = [
            "id",
            "task_id",
            "task_name",
            "correlation_id",
            "status",
            "started_at",
            "finished_at",
            "duration",
            "error_message",
            "args_summary",
            "retry_count",
            "queued_at",
            "heartbeat_at",
            "lease_expires_at",
            "queue_age_seconds",
        ]

    def get_queue_age_seconds(self, obj):
        if obj.status != "PENDING" or not obj.queued_at:
            return None
        return round((timezone.now() - obj.queued_at).total_seconds(), 1)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["args_summary"] = redact_string(data["args_summary"])
        data["error_message"] = redact_string(data["error_message"])
        return data
