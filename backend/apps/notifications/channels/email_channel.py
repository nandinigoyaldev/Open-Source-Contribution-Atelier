from __future__ import annotations

from typing import Any, Dict

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .base import DeliveryResult, NotificationChannel


class EmailChannel(NotificationChannel):
    channel_id = "email"

    def deliver(self, *, notification: Any, recipient: Any, meta: Dict[str, Any]) -> DeliveryResult:
        notif_type = getattr(notification, "notif_type", None) or meta.get("notif_type")
        title = getattr(notification, "title", "")
        message = getattr(notification, "message", "")

        template_html = None
        template_txt = None
        if notif_type:
            # <notification_type>_email.html
            try:
                template_html = render_to_string(
                    f"notifications/{notif_type}_email.html",
                    {"title": title, "message": message, "recipient": recipient, "meta": getattr(notification, "meta", {})},
                )
            except Exception:
                template_html = None

            try:
                template_txt = render_to_string(
                    f"notifications/{notif_type}_email.txt",
                    {"title": title, "message": message, "recipient": recipient, "meta": getattr(notification, "meta", {})},
                )
            except Exception:
                template_txt = None

        if template_html:
            body_html = template_html
            body_text = strip_tags(template_html)
        elif template_txt:
            body_text = template_txt
            body_html = None
        else:
            body_text = message
            body_html = None

        subject = title or f"Notification: {notif_type}"  # fallback

        if not getattr(recipient, "email", None):
            return DeliveryResult(ok=False, status="failed", error="missing_email")

        email = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=getattr(meta, "from_email", None) or None,
            to=[recipient.email],
        )
        if body_html:
            email.attach_alternative(body_html, "text/html")

        email.send(fail_silently=False)
        return DeliveryResult(ok=True, status="sent")

