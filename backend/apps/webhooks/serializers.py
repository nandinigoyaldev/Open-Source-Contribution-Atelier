from rest_framework import serializers

from .models import WebhookDelivery, WebhookDeliveryLog, WebhookEndpoint


class WebhookEndpointSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(write_only=True, required=False)
    is_circuit_open = serializers.SerializerMethodField()
    circuit_state = serializers.SerializerMethodField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "target_url",
            "is_active",
            "events",
            "secret",
            "health_status",
            "consecutive_failure_count",
            "circuit_broken_until",
            "last_failure_reason",
            "failure_threshold",
            "cooldown_seconds",
            "is_circuit_open",
            "circuit_state",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "health_status",
            "consecutive_failure_count",
            "circuit_broken_until",
            "last_failure_reason",
            "is_circuit_open",
            "circuit_state",
        ]

    def get_is_circuit_open(self, obj):
        return obj.is_circuit_open()

    def get_circuit_state(self, obj):
        return getattr(obj, "circuit_state", "CLOSED")

    def create(self, validated_data):
        secret_val = validated_data.pop("secret", None)
        instance = super().create(validated_data)
        if secret_val:
            instance.secret = secret_val
            instance.save()
        return instance

    def update(self, instance, validated_data):
        secret_val = validated_data.pop("secret", None)
        instance = super().update(instance, validated_data)
        if secret_val:
            instance.secret = secret_val
            instance.save()
        return instance


class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDeliveryLog
        fields = ["id", "status_code", "response_body", "key_id", "attempted_at"]
        read_only_fields = [
            "id",
            "status_code",
            "response_body",
            "key_id",
            "attempted_at",
        ]


class WebhookDeliverySerializer(serializers.ModelSerializer):
    logs = WebhookDeliveryLogSerializer(many=True, read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "event_type",
            "payload",
            "status",
            "status_code",
            "response_body",
            "created_at",
            "logs",
        ]
        read_only_fields = [
            "id",
            "event_type",
            "payload",
            "status",
            "status_code",
            "response_body",
            "created_at",
            "logs",
        ]
