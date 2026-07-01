from rest_framework import serializers

from .models import Notification, PushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(
        source="sender.username", read_only=True, allow_null=True
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "notif_type",
            "title",
            "message",
            "is_read",
            "created_at",
            "sender_username",
            "meta",
        ]


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ["endpoint", "p256dh", "auth"]
