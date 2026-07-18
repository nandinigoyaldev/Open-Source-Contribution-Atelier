from rest_framework import serializers

from .models import WebhookDelivery, WebhookEndpoint


class WebhookEndpointSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(write_only=True, required=False)

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
        read_only_fields = ["created_at", "updated_at"]

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
