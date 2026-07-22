import logging
import requests
from apps.notifications.channels.base import NotificationChannel

logger = logging.getLogger(__name__)


class SlackChannel(NotificationChannel):
    channel_id = "slack"

    def deliver(self, delivery, recipient, payload: dict) -> bool:
        meta = payload.get("meta", {})
        webhook_url = meta.get("slack_webhook_url")
        if not webhook_url:
            pref = getattr(recipient, "notificationpreference", None)
            webhook_url = getattr(pref, "webhook_url", None) if pref else None

        if not webhook_url or "slack.com" not in webhook_url:
            logger.info("[Slack Mock] Dispatching to Slack for %s: %s", recipient, payload.get("title"))
            return True

        text = f"*{payload.get('title')}*\n{payload.get('message')}"
        res = requests.post(webhook_url, json={"text": text}, timeout=5)
        return res.status_code == 200
