from datetime import date

import pytest
from django.contrib.auth import get_user_model

from apps.challenges.models import Challenge, ChallengeCompletion, ChallengeOfTheDay
from apps.challenges.services import (
    BASE_MULTIPLIER,
    STREAK_MULTIPLIER_THRESHOLD_DAYS,
    _streak_multiplier_for_days,
    calculate_daily_challenge_xp,
)
from apps.progress.models import StreakProfile

User = get_user_model()


@pytest.mark.django_db
class TestStreakMultiplierLookup:
    def test_streak_at_or_below_threshold_uses_base_multiplier(self):
        assert (
            _streak_multiplier_for_days(STREAK_MULTIPLIER_THRESHOLD_DAYS)
            == BASE_MULTIPLIER
        )
        assert _streak_multiplier_for_days(1) == BASE_MULTIPLIER
        assert _streak_multiplier_for_days(0) == BASE_MULTIPLIER

    def test_streak_just_above_threshold_gets_1_2x(self):
        assert _streak_multiplier_for_days(STREAK_MULTIPLIER_THRESHOLD_DAYS + 1) == 1.2

    def test_streak_respects_higher_tiers(self):
        assert _streak_multiplier_for_days(14) == 1.3
        assert _streak_multiplier_for_days(30) == 1.5

    def test_very_long_streak_caps_at_max_multiplier(self):
        assert _streak_multiplier_for_days(100) == 1.5


@pytest.mark.django_db
class TestCalculateDailyChallengeXp:
    def setup_method(self):
        self.user = User.objects.create_user(
            username="streak_challenger", password="password"
        )
        self.profile = StreakProfile.objects.create(user=self.user, current_streak=0)

    def test_no_streak_returns_base_xp(self):
        assert calculate_daily_challenge_xp(self.user, 50) == 50

    def test_streak_below_threshold_returns_base_xp(self):
        self.profile.current_streak = 3
        self.profile.save()
        assert calculate_daily_challenge_xp(self.user, 50) == 50

    def test_streak_above_threshold_applies_multiplier(self):
        self.profile.current_streak = 6
        self.profile.save()
        assert calculate_daily_challenge_xp(self.user, 50) == 60  # 50 * 1.2

    def test_higher_streak_tier_applies_bigger_multiplier(self):
        self.profile.current_streak = 14
        self.profile.save()
        assert calculate_daily_challenge_xp(self.user, 50) == 65  # 50 * 1.3

    def test_max_tier_applies_cap_multiplier(self):
        self.profile.current_streak = 30
        self.profile.save()
        assert calculate_daily_challenge_xp(self.user, 50) == 75  # 50 * 1.5

    def test_explicit_streak_argument_overrides_profile(self):
        # Profile says 0 but we pass 14 explicitly.
        assert calculate_daily_challenge_xp(self.user, 50, current_streak=14) == 65

    def test_result_is_rounded_int(self):
        # 33 * 1.3 = 42.9 -> 43
        assert calculate_daily_challenge_xp(self.user, 33, current_streak=14) == 43

    def test_user_without_profile_returns_base_xp(self):
        new_user = User.objects.create_user(username="no_profile", password="password")
        assert calculate_daily_challenge_xp(new_user, 50) == 50


@pytest.mark.django_db
class TestCompleteChallengeOfTheDayMultiplier:
    def setup_method(self):
        self.user = User.objects.create_user(
            username="daily_streak_challenger", password="password"
        )
        self.profile = StreakProfile.objects.create(
            user=self.user, current_streak=6, last_activity_date=date(2026, 8, 9)
        )

    def test_completion_applies_streak_multiplier(self):
        from unittest.mock import patch

        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)

        challenge = Challenge.objects.create(
            title="Streak Day Challenge", slug="streak-day"
        )
        ChallengeOfTheDay.objects.create(
            challenge=challenge, date="2026-08-10", bonus_points=50
        )

        # User has a 6-day streak -> 1.2x multiplier -> 60 XP
        self.profile.current_streak = 6
        self.profile.save()

        with patch(
            "django.utils.timezone.now",
            return_value=__import__("datetime").datetime(
                2026, 8, 10, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc
            ),
        ):
            response = client.post("/api/challenges/today/complete/")

        assert response.status_code == 201
        assert response.data["bonus_earned"] == 60
        completion = ChallengeCompletion.objects.get(
            user=self.user, challenge=challenge
        )
        assert completion.bonus_earned == 60
