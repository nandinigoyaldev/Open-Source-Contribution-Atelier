from rest_framework import serializers

from .models import WebhookDelivery, WebhookEndpoint


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "target_url",
            "is_active",
            "events",
            "secret",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["secret", "created_at", "updated_at"]


class WebhookDeliverySerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = [
            "id",
            "event_type",
            "payload",
            "status",
            "status_code",
            "response_body",
            "created_at",
        ]
