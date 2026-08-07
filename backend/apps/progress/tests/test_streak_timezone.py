from datetime import datetime, timezone

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import UserProfile
from apps.progress.models import DailyActivity, StreakProfile
from apps.progress.streak_engine import StreakEngine, get_user_local_date

User = get_user_model()


@pytest.mark.django_db
class TestStreakTimezoneEvaluation:
    def test_get_user_local_date_utc_plus_9(self):
        user = User.objects.create_user(username="tokyo_user", password="password")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.timezone = "Asia/Tokyo"  # UTC+9
        profile.save()

        # 2026-08-04 20:00:00 UTC = 2026-08-05 05:00:00 JST
        dt_utc = datetime(2026, 8, 4, 20, 0, 0, tzinfo=timezone.utc)
        local_date = get_user_local_date(user, dt_utc)
        assert local_date.day == 5
        assert local_date.month == 8
        assert local_date.year == 2026

    def test_get_user_local_date_utc_minus_8(self):
        user = User.objects.create_user(username="la_user", password="password")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.timezone = "America/Los_Angeles"  # UTC-7 (PDT daylight saving)
        profile.save()

        # 2026-08-05 02:00:00 UTC = 2026-08-04 19:00:00 PDT
        dt_utc = datetime(2026, 8, 5, 2, 0, 0, tzinfo=timezone.utc)
        local_date = get_user_local_date(user, dt_utc)
        assert local_date.day == 4
        assert local_date.month == 8

    def test_streak_recording_across_timezone_boundary(self):
        user = User.objects.create_user(username="tz_streak_user", password="password")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.timezone = "Asia/Tokyo"
        profile.save()

        # Day 1: 2026-08-04 14:00 UTC -> 2026-08-04 23:00 JST (Aug 4)
        dt_day1 = datetime(2026, 8, 4, 14, 0, 0, tzinfo=timezone.utc)
        res1 = StreakEngine.record_activity(user, dt_day1)
        assert res1["current_streak"] == 1

        # Day 2: 2026-08-04 20:00 UTC -> 2026-08-05 05:00 JST (Aug 5 in Tokyo!)
        dt_day2 = datetime(2026, 8, 4, 20, 0, 0, tzinfo=timezone.utc)
        res2 = StreakEngine.record_activity(user, dt_day2)
        assert res2["current_streak"] == 2

    def test_daily_activity_uses_user_timezone(self):
        user = User.objects.create_user(username="da_tz_user", password="password")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.timezone = "Asia/Tokyo"
        profile.save()

        # 2026-08-04 22:00 UTC is 2026-08-05 JST
        dt_utc = datetime(2026, 8, 4, 22, 0, 0, tzinfo=timezone.utc)
        created, streak_prof = DailyActivity.log_and_update_streak(
            user=user, date=dt_utc, activity_type="lesson"
        )
        assert created is True
        assert streak_prof.last_activity_date.day == 5
