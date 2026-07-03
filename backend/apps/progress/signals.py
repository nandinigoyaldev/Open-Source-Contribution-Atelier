import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction

from .models import ExerciseAttempt, LessonProgress

logger = logging.getLogger(__name__)



def update_user_streak(user):
    """
    Core business logic to calculate and update daily coding streaks.
    """
    from apps.progress.models import StreakProfile

    today = timezone.localdate()

    with transaction.atomic():
        profile, created = StreakProfile.objects.select_for_update().get_or_create(
            user=user
        )

        # If already updated today, do nothing
        if profile.last_activity_date == today:
            return

        # If last activity was exactly yesterday, continue the streak
        if profile.last_activity_date == today - timedelta(days=1):
            profile.current_streak += 1
        else:
            # Otherwise, the streak broke. Reset to 1.
            profile.current_streak = 1

        # Update all-time high
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak

        profile.last_activity_date = today
        profile.save(
            update_fields=[
                "current_streak",
                "longest_streak",
                "last_activity_date",
                "updated_at",
            ]
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
        update_user_streak(instance.user)
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
            lambda: async_task("apps.progress.tasks.evaluate_achievements_task", instance.user.id)
        )
    except Exception as exc:
        logger.error("Failed to enqueue achievement evaluation: %s", exc)


@receiver(post_save, sender=ExerciseAttempt)
def on_exercise_attempt(sender, instance, created, **kwargs):
    if instance.is_correct:
        # --- UPDATE STREAK ---
        try:
            update_user_streak(instance.user)
        except Exception as exc:
            logger.error("Failed to update user streak: %s", exc)

        try:
            from django_q.tasks import async_task

            transaction.on_commit(
                lambda: async_task("apps.progress.tasks.evaluate_achievements_task", instance.user.id)
            )
        except Exception as exc:
            logger.error("Failed to evaluate achievements: %s", exc)
