import hmac
import hashlib
import json
import logging
import requests
from django.conf import settings

from apps.notifications.channels.base import NotificationChannel

logger = logging.getLogger(__name__)


class WebhookChannel(NotificationChannel):
    channel_id = "webhook"

    def deliver(self, delivery, recipient, payload: dict) -> bool:
        pref = getattr(recipient, "notificationpreference", None)
        webhook_url = getattr(pref, "webhook_url", None) if pref else None
        webhook_secret = getattr(pref, "webhook_secret", None) if pref else None

        if not webhook_url:
            logger.warning("No webhook_url configured for recipient %s", recipient)
            return False

        secret = (webhook_secret or getattr(settings, "SECRET_KEY", "webhook-secret")).encode("utf-8")

        body_data = {
            "event": "notification.created",
            "delivery_id": delivery.id,
            "notif_type": payload.get("notif_type"),
            "title": payload.get("title"),
            "message": payload.get("message"),
            "meta": payload.get("meta", {}),
            "recipient_id": recipient.id,
        }
        json_payload = json.dumps(body_data, sort_keys=True)
        signature = hmac.new(secret, json_payload.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature-256": f"sha256={signature}",
            "User-Agent": "OSCA-Notification-Webhook/1.0",
        }

        try:
            resp = requests.post(webhook_url, data=json_payload, headers=headers, timeout=10)
            if resp.status_code in [200, 201, 202, 204]:
                return True
            else:
                logger.warning(
                    "Webhook to %s failed with status %s: %s", webhook_url, resp.status_code, resp.text
                )
                raise RuntimeError(f"Webhook responded with HTTP status {resp.status_code}")
        except requests.RequestException as exc:
            logger.error("Webhook POST to %s failed: %s", webhook_url, exc)
            raise exc
