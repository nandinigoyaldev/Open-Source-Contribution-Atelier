from rest_framework import serializers
from apps.monitoring.models import BackupVerification


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
