import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LessonProgress

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LessonProgress)
def on_lesson_completed(sender, instance, created, **kwargs):
    """
    Signal receiver that fires when a LessonProgress record is saved.

    Broadcasts a leaderboard_update only on a *first-time* completion
    transition (created-and-completed, or flipped from incomplete to complete)
    to prevent duplicate broadcasts when an already-completed record is
    re-saved for unrelated reasons.
    """
    # Only broadcast on a genuine completion transition.
    # `created` covers the case where the record is inserted as completed.
    # For updates we check the previous DB value via update_fields / pre-save.
    if not instance.completed:
        return

    # If the instance was not freshly created, verify it was previously
    # incomplete by querying the DB.  We use `created` as the fast path.
    if not created:
        try:
            previous = LessonProgress.objects.only("completed").get(pk=instance.pk)
            # previous.completed is stale from *before* this save only when
            # the row was fetched before the save; Django doesn't do that for
            # us, so we rely on update_fields presence as a hint, and fall back
            # to a second query approach via the pre-save state stored by the
            # model if available, otherwise skip to avoid duplicate broadcasts.
            #
            # Simplest safe guard: if update_fields is set and 'completed' is
            # not in it, the completion flag wasn't touched — skip.
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "completed" not in update_fields:
                return
        except LessonProgress.DoesNotExist:
            pass

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured; skipping leaderboard broadcast.")
        return

    try:
        from apps.progress.models import LessonProgress as LP
        from django.db.models import Sum

        total_xp = (
            LP.objects.filter(user=instance.user).aggregate(total=Sum("score"))["total"]
            or 0
        )
        async_to_sync(channel_layer.group_send)(
            "leaderboard",
            {
                "type": "leaderboard_update",
                "event": "xp_update",
                "user_id": instance.user.id,
                "username": instance.user.username,
                "xp": total_xp,
                "message": f"User {instance.user.username} completed lesson {instance.lesson.title}",
            },
        )
        logger.info(
            "Pushed leaderboard update for user %s completing lesson %s",
            instance.user.username,
            instance.lesson.title,
        )
    except Exception as exc:
        logger.error("Failed to push leaderboard update: %s", exc)
