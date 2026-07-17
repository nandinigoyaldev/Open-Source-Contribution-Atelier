from __future__ import annotations

import hmac
import hashlib
import json
from typing import Any, Dict

import requests

from .base import DeliveryResult, NotificationChannel


class WebhookChannel(NotificationChannel):
    channel_id = "webhook"

    def deliver(self, *, notification: Any, recipient: Any, meta: Dict[str, Any]) -> DeliveryResult:
        # Expected endpoint and per-user secret provided via meta.
        endpoint = meta.get("endpoint")
        secret = meta.get("secret")
        if not endpoint or not secret:
            return DeliveryResult(ok=False, status="failed", error="missing_webhook_config")

        payload = {
            "notification": {
                "notif_type": getattr(notification, "notif_type", None),
                "title": getattr(notification, "title", None),
                "message": getattr(notification, "message", None),
                "meta": getattr(notification, "meta", {}) or {},
            },
            "recipient": {"id": recipient.id},
        }

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        try:
            resp = requests.post(
                endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature-256": signature,
                },
                timeout=10,
            )
        except Exception as exc:
            return DeliveryResult(ok=False, status="failed", error=str(exc))

        if resp.status_code >= 200 and resp.status_code < 300:
            return DeliveryResult(ok=True, status="sent")

        return DeliveryResult(ok=False, status="failed", error=f"http_{resp.status_code}")

