import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush  # type: ignore

from apps.notifications.channels.base import DeliveryResult, NotificationChannel
from apps.notifications.models import PushSubscription
from apps.notifications.vapid import DEFAULT_VAPID_ADMIN_EMAIL, build_vapid_claims

logger = logging.getLogger(__name__)


class PushChannel(NotificationChannel):
    channel_id = "push"

    def deliver(self, delivery, recipient, payload: dict) -> DeliveryResult:
        subscriptions = PushSubscription.objects.filter(user=recipient)
        if not subscriptions.exists():
            logger.info("No push subscriptions found for recipient %s", recipient)
            return DeliveryResult.permanent_failure(
                "No push subscriptions found", provider="webpush"
            )

        vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
        vapid_admin_email = (
            getattr(settings, "VAPID_ADMIN_EMAIL", None) or DEFAULT_VAPID_ADMIN_EMAIL
        )

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
            return DeliveryResult.sent(
                provider="webpush",
                response={"mock": True, "count": subscriptions.count()},
            )

        delivered_count = 0
        retired_count = 0
        last_error = None
        last_status = None

        for sub in list(subscriptions):
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=push_payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims=build_vapid_claims(vapid_admin_email),
                )
                delivered_count += 1
            except WebPushException as ex:
                status = getattr(getattr(ex, "response", None), "status_code", None)
                if status in [404, 410]:
                    sub.delete()
                    retired_count += 1
                else:
                    logger.warning("WebPush failed for sub %s: %s", sub.id, ex)
                    last_error = ex
                    last_status = status
            except Exception as exc:
                logger.error("Error sending webpush: %s", exc)
                last_error = exc

        if delivered_count > 0:
            return DeliveryResult.sent(
                provider="webpush",
                response={"delivered": delivered_count, "retired": retired_count},
            )

        if (
            retired_count > 0
            and not PushSubscription.objects.filter(user=recipient).exists()
        ):
            return DeliveryResult.permanent_failure(
                "All push subscriptions expired or invalid (404/410)",
                provider="webpush",
            )

        if last_error:
            is_transient = True
            if (
                last_status
                and 400 <= last_status < 500
                and last_status not in [408, 409, 429]
            ):
                is_transient = False
            if is_transient:
                return DeliveryResult.transient_failure(
                    str(last_error),
                    provider="webpush",
                    status_code=last_status,
                )
            return DeliveryResult.permanent_failure(
                str(last_error),
                provider="webpush",
                status_code=last_status,
            )

        return DeliveryResult.permanent_failure(
            "No active push endpoints could be reached", provider="webpush"
        )
