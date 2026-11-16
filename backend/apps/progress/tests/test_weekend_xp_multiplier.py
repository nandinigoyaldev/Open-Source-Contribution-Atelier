from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.progress.models import StreakProfile
from apps.progress.streak_engine import StreakEngine

User = get_user_model()


@pytest.mark.django_db
class TestWeekendXpBonusMultiplier:
    def setup_method(self):
        self.user = User.objects.create_user(
            username="weekend_warrior", password="password"
        )
        self.profile = StreakEngine.get_or_create_profile(self.user)

    def test_is_weekend_event_detection(self):
        # 2026-08-22 is Saturday (weekday=5)
        saturday = date(2026, 8, 22)
        assert StreakEngine.is_weekend_event(saturday) is True

        # 2026-08-23 is Sunday (weekday=6)
        sunday = date(2026, 8, 23)
        assert StreakEngine.is_weekend_event(sunday) is True

        # 2026-08-21 is Friday (weekday=4)
        friday = date(2026, 8, 21)
        assert StreakEngine.is_weekend_event(friday) is False

        # 2026-08-24 is Monday (weekday=0)
        monday = date(2026, 8, 24)
        assert StreakEngine.is_weekend_event(monday) is False

    def test_multiplier_calculation_with_weekend_bonus(self):
        # Baseline: streak 1 day on weekday -> 1.0x
        weekday = date(2026, 8, 19)  # Wednesday
        assert StreakEngine.get_multiplier_for_streak(1, weekday) == 1.0

        # Weekend: streak 1 day on Saturday -> 1.0x * 1.5 = 1.5x
        saturday = date(2026, 8, 22)
        assert StreakEngine.get_multiplier_for_streak(1, saturday) == 1.5

        # 3-day milestone is 1.1x -> on weekend: 1.1 * 1.5 = 1.65x
        assert StreakEngine.get_multiplier_for_streak(3, saturday) == 1.65

        # 7-day milestone is normally 1.25x -> on weekend: 1.25 * 1.5 = 1.88x (rounded to 2 decimal places)
        assert StreakEngine.get_multiplier_for_streak(7, saturday) == 1.88

        # 14-day milestone is 1.5x -> on weekend: 1.5 * 1.5 = 2.25x
        assert StreakEngine.get_multiplier_for_streak(14, saturday) == 2.25

        # 30-day milestone is 2.0x -> on weekend: 2.0 * 1.5 = 3.0x
        assert StreakEngine.get_multiplier_for_streak(30, saturday) == 3.0

    def test_get_multiplier_for_user_on_weekend(self):
        # 7-day streak base multiplier is 1.25x
        self.profile.current_streak = 7
        self.profile.save()

        saturday = date(2026, 8, 22)
        effective = StreakEngine.get_multiplier_for_user(self.user, saturday)
        assert effective == 1.88  # 1.25 * 1.5 = 1.88

        friday = date(2026, 8, 21)
        effective_weekday = StreakEngine.get_multiplier_for_user(self.user, friday)
        assert effective_weekday == 1.25

    def test_get_multiplier_for_nonexistent_profile(self):
        new_user = User.objects.create_user(username="ghost_user", password="password")
        saturday = date(2026, 8, 22)
        effective = StreakEngine.get_multiplier_for_user(new_user, saturday)
        assert effective == 1.5

        monday = date(2026, 8, 24)
        effective_weekday = StreakEngine.get_multiplier_for_user(new_user, monday)
        assert effective_weekday == 1.0

    def test_streak_status_api_endpoint_includes_weekend_fields(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        res = client.get("/api/progress/streak/")
        assert res.status_code == 200
        assert "effective_multiplier" in res.data
        assert "is_weekend_event" in res.data

    def test_record_activity_preserves_streak_and_applies_multipliers(self):
        # Record activity on Saturday
        sat = date(2026, 8, 22)
        res_sat = StreakEngine.record_activity(self.user, sat)
        assert res_sat["current_streak"] == 1
        assert "effective_multiplier" in res_sat

        # Record activity on Sunday
        sun = date(2026, 8, 23)
        res_sun = StreakEngine.record_activity(self.user, sun)
        assert res_sun["current_streak"] == 2
        assert "effective_multiplier" in res_sun

    def test_streak_status_and_getter_frozen_clock_weekday_and_weekend(self):
        # 7-day streak base milestone is 1.25x
        self.profile.current_streak = 7  # type: ignore[assignment]
        self.profile.longest_streak = 7  # type: ignore[assignment]
        self.profile.save()

        # Friday: expected=1.25, effective_multiplier=1.25, is_weekend=False
        friday = datetime(2026, 8, 21, 12, tzinfo=timezone.utc)
        with patch("django.utils.timezone.now", return_value=friday):
            data_fri = StreakEngine.get_streak_data(self.user)
            getter_fri = StreakEngine.get_multiplier_for_user(self.user)
            expected_fri = StreakEngine.get_multiplier_for_streak(7, friday.date())
            assert expected_fri == 1.25
            assert data_fri["effective_multiplier"] == 1.25
            assert getter_fri == 1.25
            assert data_fri["is_weekend_event"] is False

        # Saturday: expected=1.88, effective_multiplier=1.88 (not 2.82), is_weekend=True
        saturday = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
        with patch("django.utils.timezone.now", return_value=saturday):
            data_sat = StreakEngine.get_streak_data(self.user)
            getter_sat = StreakEngine.get_multiplier_for_user(self.user)
            expected_sat = StreakEngine.get_multiplier_for_streak(7, saturday.date())
            assert expected_sat == 1.88
            assert data_sat["effective_multiplier"] == 1.88
            assert getter_sat == 1.88
            assert data_sat["is_weekend_event"] is True

        # Sunday: expected=1.88, effective_multiplier=1.88 (not 2.82), is_weekend=True
        sunday = datetime(2026, 8, 23, 12, tzinfo=timezone.utc)
        with patch("django.utils.timezone.now", return_value=sunday):
            data_sun = StreakEngine.get_streak_data(self.user)
            getter_sun = StreakEngine.get_multiplier_for_user(self.user)
            expected_sun = StreakEngine.get_multiplier_for_streak(7, sunday.date())
            assert expected_sun == 1.88
            assert data_sun["effective_multiplier"] == 1.88
            assert getter_sun == 1.88
            assert data_sun["is_weekend_event"] is True

        # Monday: expected=1.25, effective_multiplier=1.25, is_weekend=False
        monday = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
        with patch("django.utils.timezone.now", return_value=monday):
            data_mon = StreakEngine.get_streak_data(self.user)
            getter_mon = StreakEngine.get_multiplier_for_user(self.user)
            expected_mon = StreakEngine.get_multiplier_for_streak(7, monday.date())
            assert expected_mon == 1.25
            assert data_mon["effective_multiplier"] == 1.25
            assert getter_mon == 1.25
            assert data_mon["is_weekend_event"] is False

    def test_get_multiplier_for_user_explicit_date_differs_from_system_date(self):
        # 7-day streak base milestone is 1.25x
        self.profile.current_streak = 7  # type: ignore[assignment]
        self.profile.save()

        # System clock frozen on Saturday (weekend)
        saturday_sys = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
        with patch("django.utils.timezone.now", return_value=saturday_sys):
            # Querying with explicit weekday date must return weekday multiplier 1.25x
            explicit_monday = date(2026, 8, 24)
            assert (
                StreakEngine.get_multiplier_for_user(self.user, explicit_monday) == 1.25
            )

        # System clock frozen on Wednesday (weekday)
        wednesday_sys = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
        with patch("django.utils.timezone.now", return_value=wednesday_sys):
            # Querying with explicit weekend date must return weekend multiplier 1.88x
            explicit_sunday = date(2026, 8, 23)
            assert (
                StreakEngine.get_multiplier_for_user(self.user, explicit_sunday) == 1.88
            )
