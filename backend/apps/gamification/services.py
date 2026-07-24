from datetime import timedelta

from django.utils import timezone

from .models import Streak


class StreakService:
    @staticmethod
    def update_streak(user):
        streak, created = Streak.objects.get_or_create(user=user)
        today = timezone.localdate()

        if streak.last_activity_date == today:
            return streak  # Already updated today

        if streak.last_activity_date == today - timedelta(days=1):
            streak.current_streak += 1
        else:
            streak.current_streak = 1

        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak

        streak.last_activity_date = today
        streak.save()
        return streak
