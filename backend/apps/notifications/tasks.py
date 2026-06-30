import json

from celery import shared_task  # type: ignore
from django.conf import settings
from django.core.mail import send_mail
from pywebpush import WebPushException, webpush  # type: ignore

from .models import PushSubscription


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_web_push_notification(self, user_id, title, message, url=None):
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
                # Log the exception or handle retry if appropriate
                pass
        except Exception:
            pass


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_bulk_email(self, payload):
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

    if template_id == "weekly_progress_summary":
        subject = "Your Weekly Progress Summary"
        message = (
            f"Hi {data.get('username')},\n\n"
            f"Here is your progress over the last 7 days:\n"
            f"- Lessons completed: {data.get('lessons_completed', 0)}\n"
            f"- XP earned: {data.get('xp_earned', 0)}\n"
            f"- Badges earned: {data.get('badges_earned', 0)}\n"
        )
        if data.get("badge_names"):
            badges_str = ", ".join(data["badge_names"])
            message += f"- New badges: {badges_str}\n"

        message += "\nKeep up the great work!\n"

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)
