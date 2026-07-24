"""
Signals that fire when:
  1. A Badge is awarded to a user  →  badge notification
  2. A Comment is posted on a contribution  →  comment notification

Adapt the sender models to match the actual models in apps/
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)


def _push_notification(notification: Notification):
    """Send a notification object to the user's WebSocket group."""
    from apps.core.channel_safety import safe_group_send_sync

    data = NotificationSerializer(notification).data
    group_name = f"notifications_{notification.recipient_id}"  # type: ignore
    pushed = safe_group_send_sync(
        group_name,
        {
            "type": "send_notification",  # matches consumer method
            "notification": data,
        },
    )
    if pushed:
        logger.info(
            "Pushed notification id=%s to group=%s",
            notification.id,  # type: ignore
            group_name,
        )
    else:
        logger.warning(
            "Skipped WS push for notification id=%s (channel layer unavailable)",
            notification.id,  # type: ignore
        )

    # Dispatch web push notification asynchronously
    try:
        url = "/"
        if notification.notif_type == "badge":
            url = "/profile"
        elif notification.meta and "contribution_id" in notification.meta:  # type: ignore
            url = f"/contributions/{notification.meta['contribution_id']}"  # type: ignore

        async_task(
            "apps.notifications.tasks.send_web_push_notification",
            user_id=notification.recipient_id,  # type: ignore
            title=notification.title,
            message=notification.message,
            url=url,
        )
    except Exception as exc:
        logger.error("Failed to enqueue web push notification: %s", exc)


# ------------------------------------------------------------------ #
# Badge signal                                                        #
# ------------------------------------------------------------------ #
from apps.progress.models import UserBadge


@receiver(post_save, sender=UserBadge, dispatch_uid="on_badge_awarded_notification")
def on_badge_awarded(sender, instance, created, **kwargs):
    if not created:
        return
    notif = Notification.objects.create(
        recipient=instance.user,
        notif_type="badge",
        title="🏅 New Badge Earned!",
        message=f"You earned the '{instance.badge.name}' badge.",
        meta={
            "badge_id": instance.badge.id,
            "badge_name": instance.badge.name,
            "badge_slug": instance.badge.slug,
        },
    )
    _push_notification(notif)

    # Offload bulk email or notification digest to the independent worker
    import sys

    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return

    async_task(
        "apps.notifications.tasks.send_bulk_email",
        payload={
            "template_id": "badge_earned_email",
            "recipients": [instance.user.email],
            "data": {
                "badge_name": instance.badge.name,
                "username": instance.user.username,
            },
        },
    )


# ------------------------------------------------------------------ #
# PeerReview signal
# ------------------------------------------------------------------ #
from apps.progress.models import PeerReview
from django_q.tasks import async_task


@receiver(post_save, sender=PeerReview, dispatch_uid="on_peer_review_submitted")
def on_peer_review_submitted(sender, instance, created, **kwargs):
    if not created:
        return
    submission_owner = instance.submission.user
    if submission_owner == instance.reviewer:
        return  # don't notify self
    notif = Notification.objects.create(
        recipient=submission_owner,
        sender=instance.reviewer,
        notif_type="comment",
        title="👀 New Peer Review",
        message=f'{instance.reviewer.username} reviewed your submission: "{instance.feedback[:80]}"',
        meta={"submission_id": instance.submission.id, "review_id": instance.id},
    )
    _push_notification(notif)

    # Offload email notification to independent worker
    import sys

    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return

    async_task(
        "apps.notifications.tasks.send_bulk_email",
        payload={
            "template_id": "comment_posted_email",
            "recipients": [submission_owner.email],
            "data": {
                "reviewer_name": instance.reviewer.username,
                "feedback": instance.feedback[:100],
                "username": submission_owner.username,
            },
        },
    )


# ------------------------------------------------------------------ #
# Utility: call this anywhere in your codebase to send a manual notif #
# ------------------------------------------------------------------ #
def create_and_push_notification(
    recipient, notif_type, title, message, sender=None, meta=None
):
    notif = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notif_type=notif_type,
        title=title,
        message=message,
        meta=meta or {},
    )
    _push_notification(notif)
    return notif
