from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.dashboard.models import Issue, PullRequest
from apps.progress.badge_evaluator import BadgeEvaluator
from apps.progress.models import ExerciseAttempt, LessonProgress


def clear_dashboard_caches(user_id=None):
    # Always clear the global admin stats cache
    cache.delete("dashboard_admin_stats_v2")

    # If a specific user is affected, clear their specific contributor stats cache
    if user_id:
        cache.delete(f"dashboard_contributor_stats_{user_id}")
        cache.delete(f"dashboard_contributor_personal_stats_{user_id}")
        cache.delete(f"dashboard_contributor_assigned_issues_{user_id}")
        cache.delete(f"dashboard_contributor_recent_prs_{user_id}")
        cache.delete(f"dashboard_contributor_progress_tracker_{user_id}")


@receiver(pre_save, sender=Issue)
def handle_issue_pre_save(sender, instance, **kwargs):
    if instance.id:
        try:
            old_instance = Issue.objects.get(id=instance.id)
            if (
                old_instance.status != Issue.Status.SOLVED
                and instance.status == Issue.Status.SOLVED
            ):
                from apps.progress.models import XPMultiplierEvent

                multiplier = XPMultiplierEvent.get_active_multiplier()
                if multiplier > 1.0:
                    instance.bonus_points = int(instance.points * (multiplier - 1.0))
            elif (
                old_instance.status == Issue.Status.SOLVED
                and instance.status != Issue.Status.SOLVED
            ):
                instance.bonus_points = 0
        except Issue.DoesNotExist:
            pass


@receiver([post_save, post_delete], sender=Issue)
def handle_issue_change(sender, instance, **kwargs):
    # Clear cache for the assigned contributor if exists
    user_id = instance.assigned_to.id if instance.assigned_to else None
    clear_dashboard_caches(user_id=user_id)

    if (
        getattr(instance, "status", None) == Issue.Status.SOLVED
        and instance.assigned_to
    ):
        _broadcast_xp_update(instance.assigned_to)


@receiver([post_save, post_delete], sender=PullRequest)
def handle_pr_change(sender, instance, **kwargs):
    # Clear cache for the contributor who created the PR
    clear_dashboard_caches(user_id=instance.user.id)
    BadgeEvaluator.evaluate(instance.user)


@receiver([post_save, post_delete], sender=LessonProgress)
def handle_progress_change(sender, instance, **kwargs):
    # Clear cache for the contributor who completed the lesson
    clear_dashboard_caches(user_id=instance.user.id)

    if getattr(instance, "completed", False):
        _broadcast_xp_update(instance.user)

    BadgeEvaluator.evaluate(instance.user)


@receiver([post_save, post_delete], sender=ExerciseAttempt)
def handle_exercise_attempt_change(sender, instance, **kwargs):
    clear_dashboard_caches(user_id=instance.user.id)
    BadgeEvaluator.evaluate(instance.user)


def _broadcast_xp_update(user):
    lesson_xp = (
        LessonProgress.objects.filter(user=user, completed=True).aggregate(
            total=Sum("score")
        )["total"]
        or 0
    )
    issues_agg = Issue.objects.filter(
        assigned_to=user, status=Issue.Status.SOLVED
    ).aggregate(p_sum=Sum("points"), b_sum=Sum("bonus_points"))
    issues_xp = (issues_agg["p_sum"] or 0) + (issues_agg["b_sum"] or 0)
    total_xp = lesson_xp + issues_xp

    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            "leaderboard_updates",
            {
                "type": "leaderboard_update",
                "event": "xp_update",
                "user_id": user.id,
                "username": user.username,
                "xp": total_xp,
            },
        )
