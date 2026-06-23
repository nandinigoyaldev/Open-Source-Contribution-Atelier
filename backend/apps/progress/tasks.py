from celery import shared_task # type: ignore
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.progress.models import LessonProgress, UserBadge
from celery import current_app # type: ignore

User = get_user_model()

@shared_task
def send_weekly_progress_summary():
    """
    Celery cron task to calculate learning progress over the past 7 days 
    for each active user, and dispatch an email summary.
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Process active users in chunks
    users = User.objects.filter(is_active=True).iterator(chunk_size=100)

    for user in users:
        # Get progress in the last 7 days
        recent_progress = LessonProgress.objects.filter(
            user=user, 
            updated_at__gte=seven_days_ago, 
            completed=True
        )
        
        recent_badges = UserBadge.objects.filter(
            user=user, 
            earned_at__gte=seven_days_ago
        )
        
        lessons_completed = recent_progress.count()
        xp_earned = sum(progress.score for progress in recent_progress)
        badges_earned = recent_badges.count()
        badge_names = [ub.badge.name for ub in recent_badges]

        if lessons_completed > 0 or badges_earned > 0:
            payload = {
                "template_id": "weekly_progress_summary",
                "recipients": [user.email],
                "data": {
                    "username": user.username,
                    "lessons_completed": lessons_completed,
                    "xp_earned": xp_earned,
                    "badges_earned": badges_earned,
                    "badge_names": badge_names,
                }
            }
            
            # Dispatch email using the existing bulk email worker
            current_app.send_task(
                "tasks.send_bulk_email",
                kwargs={"payload": payload}
            )
