import logging
import re
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.notifications.channels.base import NotificationChannel

logger = logging.getLogger(__name__)


class EmailChannel(NotificationChannel):
    channel_id = "email"

    def deliver(self, delivery, recipient, payload: dict) -> bool:
        recipient_email = getattr(recipient, "email", None)
        if not recipient_email:
            logger.warning("Recipient %s has no email address", recipient)
            return False

        notif_type = payload.get("notif_type", "default")
        title = payload.get("title", "New Notification")
        message_text = payload.get("message", "")
        meta = payload.get("meta", {})

        context = {
            "title": title,
            "message": message_text,
            "recipient": recipient,
            "meta": meta,
            "delivery": delivery,
        }

        template_name = f"notifications/{notif_type}_email.html"
        try:
            html_content = render_to_string(template_name, context)
        except Exception:
            try:
                html_content = render_to_string(
                    "notifications/default_email.html", context
                )
            except Exception:
                html_content = (
                    f"<html><body><h2>{title}</h2><p>{message_text}</p></body></html>"
                )

        backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")

        # 1. Embed 1x1 tracking pixel
        open_tracking_url = f"{backend_url}/api/notifications/track/open/{delivery.id}/"
        tracking_pixel = f'<img src="{open_tracking_url}" width="1" height="1" alt="" style="display:none;" />'
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{tracking_pixel}</body>")
        else:
            html_content += tracking_pixel

        # 2. Click tracking link replacement
        def wrap_url(match):
            original_url = match.group(0)
            if "track/open" in original_url or "track/click" in original_url:
                return original_url
            encoded = quote(original_url, safe="")
            return f"{backend_url}/api/notifications/track/click/{delivery.id}/?target={encoded}"

        # Replace href="http..." links in HTML
        html_content = re.sub(
            r'href=["\'](https?://[^"\']+)["\']',
            lambda m: f'href="{wrap_url(m.group(1))}"',
            html_content,
        )

        plain_text = strip_tags(html_content) or message_text

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev")
        msg = EmailMultiAlternatives(
            subject=title,
            body=plain_text,
            from_email=from_email,
            to=[recipient_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True
