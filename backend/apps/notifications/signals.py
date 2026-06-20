"""
Signals that fire when:
  1. A Badge is awarded to a user  →  badge notification
  2. A Comment is posted on a contribution  →  comment notification

Adapt the sender models to match the actual models in apps/
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

channel_layer = get_channel_layer()


def _push_notification(notification: Notification):
    """Send a notification object to the user's WebSocket group."""
    data = NotificationSerializer(notification).data
    group_name = f"notifications_{notification.recipient_id}"
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type":         "send_notification",   # matches consumer method
                "notification": data,
            },
        )
        logger.info("Pushed notification id=%s to group=%s", notification.id, group_name)
    except Exception as exc:
        logger.error("Failed to push notification: %s", exc)


# ------------------------------------------------------------------ #
# Badge signal                                                        #
# ------------------------------------------------------------------ #
from apps.progress.models import UserBadge

@receiver(post_save, sender=UserBadge)
def on_badge_awarded(sender, instance, created, **kwargs):
    if not created:
        return
    notif = Notification.objects.create(
        recipient  = instance.user,
        notif_type = "badge",
        title      = "🏅 New Badge Earned!",
        message    = f"You earned the '{instance.badge.name}' badge.",
        meta       = {
            "badge_id": instance.badge.id,
            "badge_name": instance.badge.name,
            "badge_slug": instance.badge.slug
        },
    )
    _push_notification(notif)


# ------------------------------------------------------------------ #
# Comment signal                                                      #
# ------------------------------------------------------------------ #
# Uncomment and adjust once you have the Comment model
#
# from apps.contributions.models import Comment   # <- your real import
#
# @receiver(post_save, sender=Comment)
# def on_comment_posted(sender, instance, created, **kwargs):
#     if not created:
#         return
#     contribution_owner = instance.contribution.author
#     if contribution_owner == instance.author:
#         return   # don't notify self
#     notif = Notification.objects.create(
#         recipient  = contribution_owner,
#         sender     = instance.author,
#         notif_type = "comment",
#         title      = "💬 New Comment on Your Contribution",
#         message    = f"{instance.author.username} commented: \"{instance.body[:80]}\"",
#         meta       = {"contribution_id": instance.contribution.id, "comment_id": instance.id},
#     )
#     _push_notification(notif)


# ------------------------------------------------------------------ #
# Utility: call this anywhere in your codebase to send a manual notif #
# ------------------------------------------------------------------ #
def create_and_push_notification(recipient, notif_type, title, message, sender=None, meta=None):
    notif = Notification.objects.create(
        recipient  = recipient,
        sender     = sender,
        notif_type = notif_type,
        title      = title,
        message    = message,
        meta       = meta or {},
    )
    _push_notification(notif)
    return notif
