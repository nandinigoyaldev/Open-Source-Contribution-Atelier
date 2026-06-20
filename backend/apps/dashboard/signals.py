from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models import Sum
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.dashboard.models import Issue, PullRequest
from apps.progress.models import LessonProgress


def clear_dashboard_caches(user_id=None):
    # Always clear the global admin stats cache
    cache.delete("dashboard_admin_stats_v2")
    
    # If a specific user is affected, clear their specific contributor stats cache
    if user_id:
        cache.delete(f"dashboard_contributor_stats_{user_id}")


@receiver([post_save, post_delete], sender=Issue)
def handle_issue_change(sender, instance, **kwargs):
    # Clear cache for the assigned contributor if exists
    user_id = instance.assigned_to.id if instance.assigned_to else None
    clear_dashboard_caches(user_id=user_id)
    
    if getattr(instance, "status", None) == Issue.Status.SOLVED and instance.assigned_to:
        _broadcast_xp_update(instance.assigned_to)


@receiver([post_save, post_delete], sender=PullRequest)
def handle_pr_change(sender, instance, **kwargs):
    # Clear cache for the contributor who created the PR
    clear_dashboard_caches(user_id=instance.user.id)


@receiver([post_save, post_delete], sender=LessonProgress)
def handle_progress_change(sender, instance, **kwargs):
    # Clear cache for the contributor who completed the lesson
    clear_dashboard_caches(user_id=instance.user.id)
    
    if getattr(instance, "completed", False):
        _broadcast_xp_update(instance.user)

def _broadcast_xp_update(user):
    lesson_xp = LessonProgress.objects.filter(user=user, completed=True).aggregate(
        total=Sum("score")
    )["total"] or 0
    issues_xp = Issue.objects.filter(assigned_to=user, status=Issue.Status.SOLVED).aggregate(
        total=Sum("points")
    )["total"] or 0
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
            }
        )
