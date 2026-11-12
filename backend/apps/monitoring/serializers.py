from rest_framework import serializers

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
        ]
