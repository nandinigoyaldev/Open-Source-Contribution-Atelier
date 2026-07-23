from rest_framework import serializers
from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "actor",
            "actor_username",
            "action",
            "resource_type",
            "resource_id",
            "before",
            "after",
            "correlation_id",
            "ip_address",
            "user_agent",
            "created_at",
            "extra",
        ]
        read_only_fields = fields
