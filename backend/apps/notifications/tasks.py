import json
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from pywebpush import WebPushException, webpush  # type: ignore

from .models import PushSubscription

logger = logging.getLogger(__name__)


def send_web_push_notification(user_id, title, message, url=None):
    """
    Sends a Web Push notification to all subscribed endpoints for a user.
    """
    subscriptions = PushSubscription.objects.filter(user_id=user_id)
    if not subscriptions.exists():
        return

    vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
    vapid_admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", None)

    if not vapid_private_key or not vapid_admin_email:
        # VAPID not configured
        return

    payload_data = {
        "title": title,
        "message": message,
    }
    if url:
        payload_data["url"] = url

    payload = json.dumps(payload_data)

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_admin_email},
            )
        except WebPushException as ex:
            # If the endpoint is no longer valid (e.g. 410 Gone, or 404 Not Found),
            # remove it from the database.
            if ex.response and ex.response.status_code in [404, 410]:
                sub.delete()
            else:
                logger.warning("Web push failed for subscription %s: %s", sub.id, ex)
        except Exception as exc:
            logger.warning(
                "Unexpected error sending web push to user %s: %s", user_id, exc
            )


def send_bulk_email(payload):
    """
    Sends bulk emails based on payload data.
    """
    template_id = payload.get("template_id")
    recipients = payload.get("recipients", [])
    data = payload.get("data", {})

    if not recipients:
        return

    subject = "Open Source Contribution Atelier Update"
    message = "You have an update from OSCA."
    html_message = None
    pdf_attachment = None

    if template_id == "weekly_progress_summary":
        subject = f"Your Weekly Progress Summary, {data.get('username')} 📊"
        if data.get('xp_earned', 0) > 0:
            subject = f"Wow, {data['xp_earned']} XP this week, {data['username']}! 🚀"
        elif data.get('current_streak', 0) > 0:
            subject = f"Don't lose your {data['current_streak']}-day streak, {data['username']}! 🔥"
            
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from apps.progress.services.pdf_report_service import PDFReportGenerator
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user_email = recipients[0] if recipients else None
        
        html_message = render_to_string('notifications/weekly_digest.html', data)
        message = strip_tags(html_message)
        
        # Generate PDF attachment if a single user is matched
        if user_email:
            user = User.objects.filter(email=user_email).first()
            if user:
                pdf_gen = PDFReportGenerator(user)
                pdf_attachment = pdf_gen.generate()

    elif template_id == "badge_earned_email":
        badge_name = data.get("badge_name", "")
        username = data.get("username", "")
        subject = "🏅 You Earned a New Badge!"
        message = (
            f"Hi {username},\n\n"
            f"Congratulations! You earned the '{badge_name}' badge.\n\n"
            "Keep up the great work!"
        )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev")
    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=from_email,
        to=recipients
    )
    if html_message:
        email.attach_alternative(html_message, "text/html")
    
    if pdf_attachment:
        email.attach("OSCA_Progress_Report.pdf", pdf_attachment, "application/pdf")

    email.send(fail_silently=False)
