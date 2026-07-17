from __future__ import annotations

from typing import Any, Dict

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .base import DeliveryResult, NotificationChannel
from ..models import Notification
from ..serializers import NotificationSerializer


class InAppChannel(NotificationChannel):
    channel_id = "in_app"

    def deliver(self, *, notification: Any, recipient: Any, meta: Dict[str, Any]) -> DeliveryResult:
        # `notification` is expected to be a Notification row OR a dict-like payload.
        if isinstance(notification, Notification):
            notif_obj = notification
        else:
            notif_obj = Notification.objects.create(
                recipient=recipient,
                notif_type=meta.get("notif_type", notification.get("notif_type")),
                title=meta.get("title", notification.get("title")),
                message=meta.get("message", notification.get("message")),
                sender=meta.get("sender"),
                meta=meta.get("meta") or {},
            )

        # Push over websocket group
        try:
            channel_layer = get_channel_layer()
            data = NotificationSerializer(notif_obj).data
            group_name = f"notifications_{notif_obj.recipient_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_notification",
                    "notification": data,
                },
            )
        except Exception as exc:
            # In-app delivery is still considered "sent" because the notification row exists.
            return DeliveryResult(ok=True, status="sent", error=None, meta={"warning": str(exc)})

        return DeliveryResult(ok=True, status="sent")

