"""
Streak Engine — single-responsibility service for learning streak logic.

All public classmethods that touch the database are clearly labelled.
Pure-helper methods (multiplier calc, milestone lookup) are side-effect-free
so they are trivially unit-testable without a database.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.contrib.auth.models import User

from .models import STREAK_MILESTONES, StreakProfile

logger = logging.getLogger(__name__)


class StreakEngine:
    """
    Manages per-user learning streaks and their associated XP multipliers.

    Usage
    -----
    # Call this whenever a user completes a learning activity:
    result = StreakEngine.record_activity(user, date.today())

    # Get current multiplier for XP calculation:
    multiplier = StreakEngine.get_multiplier_for_user(user)

    # Get full streak data for the API:
    data = StreakEngine.get_streak_data(user)
    """

    # -------------------------------------------------------------------
    # Pure helpers — no DB access, fully unit-testable
    # -------------------------------------------------------------------

    @staticmethod
    def get_multiplier_for_streak(streak_days: int) -> float:
        """Return the XP multiplier for a given streak length."""
        multiplier = 1.0
        for milestone in STREAK_MILESTONES:
            if streak_days >= milestone["days"]:
                multiplier = milestone["multiplier"]
        return multiplier

    @staticmethod
    def get_next_milestone(streak_days: int) -> Optional[dict]:
        """Return the next unreached milestone dict, or None if at max."""
        for milestone in STREAK_MILESTONES:
            if streak_days < milestone["days"]:
                return milestone
        return None  # already past all milestones

    @staticmethod
    def compute_milestone_progress(streak_days: int) -> float:
        """
        Return 0–100 float representing progress toward the next milestone.

        If the user has hit all milestones, returns 100.0.
        """
        next_ms = StreakEngine.get_next_milestone(streak_days)
        if next_ms is None:
            return 100.0

        # Find the previous milestone (or 0 if none)
        prev_days = 0
        for milestone in STREAK_MILESTONES:
            if milestone["days"] < next_ms["days"]:
                prev_days = milestone["days"]

        span = next_ms["days"] - prev_days
        progress = streak_days - prev_days
        return round(min(100.0, (progress / span) * 100), 1)

    # -------------------------------------------------------------------
    # DB-touching methods
    # -------------------------------------------------------------------

    @classmethod
    def get_or_create_profile(cls, user: User) -> StreakProfile:
        """Fetch or create the StreakProfile for a user."""
        profile, _ = StreakProfile.objects.get_or_create(user=user)
        return profile

    @classmethod
    def get_multiplier_for_user(cls, user: User) -> float:
        """Return the current streak multiplier for a user (fast path via profile)."""
        try:
            profile = StreakProfile.objects.get(user=user)
            return profile.current_multiplier
        except StreakProfile.DoesNotExist:
            return 1.0

    @classmethod
    def record_activity(cls, user: User, activity_date: date) -> dict:
        """
        Record a learning activity for *user* on *activity_date* and update
        the StreakProfile accordingly.

        Returns a dict with the new streak state and a flag indicating
        whether a new multiplier tier was unlocked this call.

        Streak rules
        ~~~~~~~~~~~~
        - Same day as last activity  → no change (idempotent).
        - Next calendar day          → streak increments by 1.
        - Any other gap              → streak resets to 1.
        - longest_streak is updated whenever current_streak grows.
        """
        with transaction.atomic():
            profile = cls.get_or_create_profile(user)

            old_multiplier = profile.current_multiplier
            last = profile.last_activity_date

            if last is None:
                # First ever activity
                profile.current_streak = 1
            elif activity_date == last:
                # Already logged today — idempotent, return current state
                return cls._build_result(profile, multiplier_unlocked=False)
            elif activity_date == last + timedelta(days=1):
                # Consecutive day — extend streak
                profile.current_streak += 1
            else:
                # Gap detected — reset streak
                logger.info(
                    "Streak reset for user %s (gap from %s to %s)",
                    user.username,
                    last,
                    activity_date,
                )
                profile.current_streak = 1

            profile.last_activity_date = activity_date

            if profile.current_streak > profile.longest_streak:
                profile.longest_streak = profile.current_streak

            new_multiplier = cls.get_multiplier_for_streak(profile.current_streak)
            profile.current_multiplier = new_multiplier
            profile.save()

            multiplier_unlocked = new_multiplier > old_multiplier

            if multiplier_unlocked:
                logger.info(
                    "Streak multiplier unlocked for user %s: %.1fx → %.1fx "
                    "(streak=%d days)",
                    user.username,
                    old_multiplier,
                    new_multiplier,
                    profile.current_streak,
                )

            return cls._build_result(profile, multiplier_unlocked=multiplier_unlocked)

    @classmethod
    def get_streak_data(cls, user: User) -> dict:
        """
        Return a serialisable summary of the user's streak state.
        Used by StreakStatusView.
        """
        profile = cls.get_or_create_profile(user)
        next_ms = cls.get_next_milestone(profile.current_streak)
        progress_pct = cls.compute_milestone_progress(profile.current_streak)

        return {
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "current_multiplier": profile.current_multiplier,
            "next_milestone": (
                {
                    "days": next_ms["days"],
                    "multiplier": next_ms["multiplier"],
                    "label": next_ms["label"],
                }
                if next_ms
                else None
            ),
            "days_to_next_milestone": (
                next_ms["days"] - profile.current_streak if next_ms else None
            ),
            "milestone_progress_pct": progress_pct,
        }

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _build_result(profile: StreakProfile, multiplier_unlocked: bool) -> dict:
        next_ms = StreakEngine.get_next_milestone(profile.current_streak)
        return {
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "current_multiplier": profile.current_multiplier,
            "multiplier_unlocked": multiplier_unlocked,
            "next_milestone": next_ms,
            "milestone_progress_pct": StreakEngine.compute_milestone_progress(
                profile.current_streak
            ),
        }
