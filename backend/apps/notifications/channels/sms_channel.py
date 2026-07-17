from __future__ import annotations

from typing import Any, Dict

from .base import DeliveryResult, NotificationChannel


class SmsChannel(NotificationChannel):
    channel_id = "sms"

    def deliver(self, *, notification: Any, recipient: Any, meta: Dict[str, Any]) -> DeliveryResult:
        # Twilio integration is not enabled by default in this repo yet.
        # For now, behave as "no-op" unless configured for critical alerts.
        is_critical = meta.get("critical") or (getattr(notification, "meta", {}) or {}).get("critical")
        if not is_critical:
            return DeliveryResult(ok=True, status="sent", meta={"skipped": True})

        # Placeholder: if TWILIO vars not present, fail gracefully.
        if not getattr(meta, "twilio_configured", False):
            return DeliveryResult(ok=False, status="failed", error="twilio_not_configured")

        return DeliveryResult(ok=False, status="failed", error="twilio_not_implemented")

