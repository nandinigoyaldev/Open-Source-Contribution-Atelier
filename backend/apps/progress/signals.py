import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LessonProgress

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@receiver(post_save, sender=LessonProgress)
def on_lesson_completed(sender, instance, created, **kwargs):
    """
    Signal receiver that fires when a user completes a lesson.
    Broadcasts a message to the 'leaderboard' group.
    """
    if instance.completed:
        try:
            async_to_sync(channel_layer.group_send)(
                "leaderboard",
                {
                    "type": "leaderboard_update",
                    "message": f"User {instance.user.username} completed lesson {instance.lesson.title}",
                },
            )
            logger.info("Pushed leaderboard update for user %s completing lesson %s", instance.user.username, instance.lesson.title)
        except Exception as exc:
            logger.error("Failed to push leaderboard update: %s", exc)
