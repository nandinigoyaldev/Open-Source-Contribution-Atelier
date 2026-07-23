from datetime import timedelta

from django.utils import timezone

from .models import Quest, UserQuest


def assign_daily_quests():
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)

    daily_quests = Quest.objects.filter(is_active=True, frequency="daily")
    weekly_quests = Quest.objects.filter(is_active=True, frequency="weekly")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    active_users = User.objects.filter(is_active=True)

    for user in active_users:
        for quest in daily_quests:
            UserQuest.objects.get_or_create(
                user=user,
                quest=quest,
                assigned_at__date=today.date(),
                defaults={
                    "assigned_at": today,
                    "expires_at": tomorrow,
                },
            )
        for quest in weekly_quests:
            assigned_this_week = UserQuest.objects.filter(
                user=user,
                quest=quest,
                assigned_at__gte=today - timedelta(days=7),
            ).exists()
            if not assigned_this_week:
                UserQuest.objects.create(
                    user=user,
                    quest=quest,
                    assigned_at=today,
                    expires_at=week_end,
                )


def expire_old_quests():
    UserQuest.objects.filter(
        expires_at__lt=timezone.now(),
        completed=False,
    ).delete()
