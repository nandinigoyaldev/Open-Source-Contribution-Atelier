import logging
from apps.core.channel_safety import safe_group_send_sync
from apps.notifications.channels.base import NotificationChannel
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer

logger = logging.getLogger(__name__)


class InAppChannel(NotificationChannel):
    channel_id = "in_app"

    def deliver(self, delivery, recipient, payload: dict) -> bool:
        # Create or fetch Notification instance if not present
        notification = delivery.notification
        if not notification:
            notification = Notification.objects.create(
                recipient=recipient,
                notif_type=payload.get("notif_type", "badge"),
                title=payload.get("title", ""),
                message=payload.get("message", ""),
                meta=payload.get("meta", {}),
            )
            delivery.notification = notification
            delivery.save(update_fields=["notification"])

        data = NotificationSerializer(notification).data
        group_name = f"notifications_{recipient.id}"
        pushed = safe_group_send_sync(
            group_name,
            {
                "type": "send_notification",
                "notification": data,
            },
        )
        if pushed:
            logger.info("Pushed in-app notification %s to group %s", notification.id, group_name)
        else:
            logger.info("WS pushed skipped or saved for polling for notification %s", notification.id)

        return True
