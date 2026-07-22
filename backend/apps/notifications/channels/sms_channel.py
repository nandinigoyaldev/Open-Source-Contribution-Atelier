import logging
from django.conf import settings
from apps.notifications.channels.base import NotificationChannel

logger = logging.getLogger(__name__)


class SMSChannel(NotificationChannel):
    channel_id = "sms"

    def deliver(self, delivery, recipient, payload: dict) -> bool:
        # Check if SMS is for critical alert or allowed
        meta = payload.get("meta", {})
        is_critical = meta.get("is_critical", False) or payload.get("is_critical", False)
        
        pref = getattr(recipient, "notificationpreference", None)
        phone_number = getattr(pref, "phone_number", None) if pref else None
        if not phone_number and hasattr(recipient, "user_profile"):
            phone_number = getattr(recipient.user_profile, "phone_number", None)

        if not phone_number:
            logger.warning("No phone number configured for SMS recipient %s", recipient)
            return False

        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
        from_number = getattr(settings, "TWILIO_FROM_NUMBER", "+15005550006")

        body = f"{payload.get('title')}: {payload.get('message')}"

        if not account_sid or not auth_token:
            logger.info("[SMS Mock] Twilio credentials not set. Would send to %s: %s", phone_number, body)
            return True

        try:
            from twilio.rest import Client  # type: ignore
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=body,
                from_=from_number,
                to=phone_number,
            )
            return True
        except ImportError:
            logger.warning("Twilio package not installed, mocking SMS send to %s", phone_number)
            return True
        except Exception as exc:
            logger.error("Failed to send SMS via Twilio to %s: %s", phone_number, exc)
            raise exc
