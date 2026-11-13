import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DailyActivity, ExerciseAttempt, LessonProgress
from .streak_engine import get_user_local_date

logger = logging.getLogger(__name__)


def update_user_streak(user, *, activity_type=None):
    """Record signal-driven activity through the shared, freeze-aware ledger."""
    DailyActivity.log_and_update_streak(
        user=user,
        date=get_user_local_date(user),
        activity_type=activity_type,
    )


@receiver(post_save, sender=LessonProgress)
def on_lesson_completed(sender, instance, created, **kwargs):
    if not instance.completed:
        return

    if not created:
        try:
            previous = LessonProgress.objects.only("completed").get(pk=instance.pk)
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "completed" not in update_fields:
                return
        except LessonProgress.DoesNotExist:
            pass

    # --- UPDATE STREAK ---
    try:
        update_user_streak(instance.user, activity_type="lesson")
    except Exception as exc:
        logger.error("Failed to update user streak: %s", exc)

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured; skipping leaderboard broadcast.")
        return

    try:
        from django.db.models import Sum

        from apps.progress.models import LessonProgress as LP

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
    except Exception as exc:
        logger.error("Failed to push leaderboard update: %s", exc)

    # Evaluate achievements on lesson completion - Wrapped in on_commit to prevent mid-transaction evaluation
    try:
        from django_q.tasks import async_task

        transaction.on_commit(
            lambda: async_task(
                "apps.progress.tasks.evaluate_achievements_task", instance.user.id
            )
        )
    except Exception as exc:
        logger.error("Failed to enqueue achievement evaluation: %s", exc)


@receiver(post_save, sender=ExerciseAttempt)
def on_exercise_attempt(sender, instance, created, **kwargs):
    if instance.is_correct:
        # --- UPDATE STREAK ---
        try:
            update_user_streak(instance.user, activity_type="exercise")
        except Exception as exc:
            logger.error("Failed to update user streak: %s", exc)

        try:
            from django_q.tasks import async_task

            transaction.on_commit(
                lambda: async_task(
                    "apps.progress.tasks.evaluate_achievements_task", instance.user.id
                )
            )
        except Exception as exc:
            logger.error("Failed to evaluate achievements: %s", exc)


@receiver(post_save, sender="progress.XPEvent")
def on_xp_event(sender, instance, created, **kwargs):
    if created and instance.xp_delta > 0:
        try:
            from django.db import transaction
            from django_q.tasks import async_task

            transaction.on_commit(
                lambda: async_task(
                    "apps.progress.tasks.update_leaderboard_task",
                    instance.user.id,
                    instance.user.username,
                    instance.xp_delta,
                )
            )
        except Exception as exc:
            logger.error("Failed to enqueue leaderboard update: %s", exc)
