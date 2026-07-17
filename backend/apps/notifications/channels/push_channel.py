from __future__ import annotations

from typing import Any, Dict

from .base import DeliveryResult, NotificationChannel
from ..tasks import send_web_push_notification


class PushChannel(NotificationChannel):
    channel_id = "push"

    def deliver(self, *, notification: Any, recipient: Any, meta: Dict[str, Any]) -> DeliveryResult:
        # Reuse existing helper. `url` can be provided via meta.
        url = meta.get("url")
        try:
            send_web_push_notification(
                user_id=recipient.id,
                title=getattr(notification, "title", ""),
                message=getattr(notification, "message", ""),
                url=url,
            )
        except Exception as exc:
            return DeliveryResult(ok=False, status="failed", error=str(exc))

        return DeliveryResult(ok=True, status="sent")

