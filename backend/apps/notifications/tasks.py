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
        if data.get("xp_earned", 0) > 0:
            subject = f"Wow, {data['xp_earned']} XP this week, {data['username']}! 🚀"
        elif data.get("current_streak", 0) > 0:
            subject = f"Don't lose your {data['current_streak']}-day streak, {data['username']}! 🔥"

        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from apps.progress.services.pdf_report_service import PDFReportGenerator
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user_email = recipients[0] if recipients else None

        html_message = render_to_string("notifications/weekly_digest.html", data)
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
    elif template_id == "comment_posted_email":
        reviewer_name = data.get("reviewer_name", "")
        username = data.get("username", "")
        feedback = data.get("feedback", "")
        subject = "👀 New Peer Review on Your Submission"
        message = (
            f"Hi {username},\n\n"
            f"{reviewer_name} just left a review on your submission:\n\n"
            f'"{feedback}"\n\n'
            "Log in to the platform to see the full details!"
        )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev")
    email = EmailMultiAlternatives(
        subject=subject, body=message, from_email=from_email, to=recipients
    )
    if html_message:
        email.attach_alternative(html_message, "text/html")

    if pdf_attachment:
        email.attach("OSCA_Progress_Report.pdf", pdf_attachment, "application/pdf")

    email.send(fail_silently=False)

try:
    from celery import shared_task
except ImportError:
    shared_task = lambda x: x

@shared_task
def send_notification_digests():
    """
    Periodic task to send digest emails to users based on their timezone and preference.
    """
    from django.utils import timezone
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    import zoneinfo
    from .models import NotificationPreference, Notification

    prefs = NotificationPreference.objects.exclude(digest_frequency="none").select_related("user", "user__user_profile")
    
    for pref in prefs:
        if not pref.digest_time:
            continue
            
        user = pref.user
        try:
            tz = zoneinfo.ZoneInfo(user.user_profile.timezone)
        except Exception:
            tz = timezone.utc
            
        local_time = timezone.now().astimezone(tz)
        
        # Check if the current hour matches the user's preferred digest hour
        if local_time.hour != pref.digest_time.hour:
            continue
            
        # If weekly, only send on Monday (weekday() == 0)
        if pref.digest_frequency == "weekly" and local_time.weekday() != 0:
            continue
            
        # Fetch unread notifications
        unread_notifs = Notification.objects.filter(recipient=user, is_read=False).order_by("-created_at")
        if not unread_notifs.exists():
            continue
            
        # Group notifications
        grouped = {}
        for notif in unread_notifs:
            if notif.notif_type not in grouped:
                grouped[notif.notif_type] = []
            grouped[notif.notif_type].append(notif)
            
        # Send Email
        context = {
            "user": user,
            "grouped_notifications": grouped,
            "total_count": unread_notifs.count()
        }
        
        subject = f"Your {pref.digest_frequency.title()} Notification Digest"
        html_message = render_to_string('notifications/email/digest.html', context)
        message = strip_tags(html_message)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev")
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=from_email,
            to=[user.email]
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=True)
