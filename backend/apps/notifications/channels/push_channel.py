import json
import logging
from django.conf import settings
from pywebpush import WebPushException, webpush  # type: ignore

from apps.notifications.channels.base import NotificationChannel
from apps.notifications.models import PushSubscription

logger = logging.getLogger(__name__)


class PushChannel(NotificationChannel):
    channel_id = "push"

    def deliver(self, delivery, recipient, payload: dict) -> bool:
        subscriptions = PushSubscription.objects.filter(user=recipient)
        if not subscriptions.exists():
            logger.info("No push subscriptions found for recipient %s", recipient)
            return True  # Completed successfully (0 active subscriptions)

        vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
        vapid_admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", "admin@atelier.dev")

        title = payload.get("title", "Notification")
        message = payload.get("message", "")
        meta = payload.get("meta", {})

        push_payload = json.dumps(
            {
                "title": title,
                "body": message,
                "message": message,
                "icon": meta.get("icon", "/logo.png"),
                "data": meta,
                "delivery_id": delivery.id,
            }
        )

        if not vapid_private_key:
            logger.warning(
                "VAPID_PRIVATE_KEY not configured; mocking FCM/WebPush dispatch"
            )
            return True

        delivered_any = False
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=push_payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={"sub": f"mailto:{vapid_admin_email}"},
                )
                delivered_any = True
            except WebPushException as ex:
                if ex.response and ex.response.status_code in [404, 410]:
                    sub.delete()
                else:
                    logger.warning("WebPush failed for sub %s: %s", sub.id, ex)
            except Exception as exc:
                logger.error("Error sending webpush: %s", exc)

        return True
