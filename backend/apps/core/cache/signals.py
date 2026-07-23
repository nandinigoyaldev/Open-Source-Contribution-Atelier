import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

from apps.core.tasks import invalidate_tag_task

logger = logging.getLogger(__name__)


def get_model_safe(app_label, model_name):
    from django.apps import apps

    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None


# 1. Lesson signals
Lesson = get_model_safe("content", "Lesson")
if Lesson:

    @receiver([post_save, post_delete], sender=Lesson)
    def on_lesson_changed(sender, instance, **kwargs):
        slug = getattr(instance, "slug", "")
        if slug:
            invalidate_tag_task.delay(f"lesson:{slug}")
        invalidate_tag_task.delay("curriculum")


# 2. LessonProgress signals
LessonProgress = get_model_safe("progress", "LessonProgress")
if LessonProgress:

    @receiver([post_save, post_delete], sender=LessonProgress)
    def on_progress_changed(sender, instance, **kwargs):
        user_id = getattr(instance, "user_id", None)
        # If user relation object
        if user_id and not isinstance(user_id, int) and hasattr(user_id, "id"):
            user_id = user_id.id
        elif hasattr(instance, "user") and instance.user:
            user_id = instance.user.id

        if user_id:
            invalidate_tag_task.delay(f"user:{user_id}")
        invalidate_tag_task.delay("leaderboard:weekly")
        invalidate_tag_task.delay("leaderboard:alltime")


# 3. User signals
@receiver([post_save, post_delete], sender=User)
def on_user_changed(sender, instance, **kwargs):
    invalidate_tag_task.delay(f"user:{instance.id}")
    invalidate_tag_task.delay("leaderboard:*")


# 4. Badge changes
UserBadge = get_model_safe("progress", "UserBadge")
if UserBadge:

    @receiver([post_save, post_delete], sender=UserBadge)
    def on_user_badge_changed(sender, instance, **kwargs):
        user_id = getattr(instance, "user_id", None)
        if not isinstance(user_id, int) and hasattr(instance, "user") and instance.user:
            user_id = instance.user.id
        if user_id:
            invalidate_tag_task.delay(f"user:{user_id}")


# 5. Streak changes
Streak = get_model_safe("gamification", "Streak")
if Streak:

    @receiver([post_save, post_delete], sender=Streak)
    def on_streak_changed(sender, instance, **kwargs):
        user_id = getattr(instance, "user_id", None)
        if not isinstance(user_id, int) and hasattr(instance, "user") and instance.user:
            user_id = instance.user.id
        if user_id:
            invalidate_tag_task.delay(f"user:{user_id}")


StreakProfile = get_model_safe("progress", "StreakProfile")
if StreakProfile:

    @receiver([post_save, post_delete], sender=StreakProfile)
    def on_streak_profile_changed(sender, instance, **kwargs):
        user_id = getattr(instance, "user_id", None)
        if not isinstance(user_id, int) and hasattr(instance, "user") and instance.user:
            user_id = instance.user.id
        if user_id:
            invalidate_tag_task.delay(f"user:{user_id}")
