# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOperatorIssue=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
"""
Streak freeze rules: how a learner gets freeze tokens and how they are spent.

The balance lives in ``StreakProfile.streak_freezes``. Every change made here
happens while that row is locked with ``select_for_update`` and writes one
``StreakFreezeLedger`` entry, so two requests cannot spend the same token or the
same XP twice.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from typing import Optional

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.progress.models import (
    LessonProgress,
    StreakFreezeInventory,
    StreakFreezeLedger,
    StreakProfile,
    WeeklyGoal,
    XPEvent,
)

logger = logging.getLogger(__name__)

DEFAULT_FREEZE_PRICE_XP = 150
# Learners edit their own weekly targets, so a free token needs at least this
# many lessons however low the target is set.
MIN_WEEKLY_LESSONS = 5

Entry = StreakFreezeLedger.EntryType


class InsufficientXP(Exception):
    def __init__(self, price: int, balance: int):
        self.price = price
        self.balance = balance
        super().__init__(f"Not enough XP. You need {price} XP but have {balance}")


def lock_profile(user) -> StreakProfile:
    """Lock the user's streak row until the surrounding transaction ends."""
    profile, _ = StreakProfile.objects.select_for_update().get_or_create(user=user)
    return profile


def xp_balance(user) -> int:
    return (
        XPEvent.objects.filter(user=user).aggregate(total=Sum("xp_delta"))["total"] or 0
    )


def freeze_price() -> int:
    """Price of the cheapest active shop freeze, so both ways to buy cost the same."""
    from apps.gamification.models import ShopItem

    cost = (
        ShopItem.objects.filter(item_type="streak_freeze", is_active=True)
        .order_by("cost")
        .values_list("cost", flat=True)
        .first()
    )
    return DEFAULT_FREEZE_PRICE_XP if cost is None else cost


def _bump_inventory(user_id: int, field: str, amount: int) -> None:
    inventory, _ = StreakFreezeInventory.objects.get_or_create(user_id=user_id)
    StreakFreezeInventory.objects.filter(pk=inventory.pk).update(
        **{field: F(field) + amount, "updated_at": timezone.now()}
    )


def grant_freeze(
    user,
    entry_type: str,
    *,
    xp_spent: int = 0,
    week_start: Optional[date] = None,
) -> StreakFreezeLedger:
    """Add one token. The caller is responsible for charging or checking eligibility."""
    with transaction.atomic():
        profile = lock_profile(user)
        profile.streak_freezes += 1
        profile.save(update_fields=["streak_freezes", "updated_at"])
        earned = entry_type == Entry.WEEKLY_GOAL
        _bump_inventory(
            profile.user_id, "total_earned" if earned else "total_redeemed", 1
        )
        return StreakFreezeLedger.objects.create(
            user_id=profile.user_id,
            entry_type=entry_type,
            delta=1,
            balance_after=profile.streak_freezes,
            xp_spent=xp_spent,
            week_start=week_start,
        )


def redeem_with_xp(user) -> StreakFreezeLedger:
    """Spend XP on one freeze token. Raises InsufficientXP."""
    with transaction.atomic():
        lock_profile(user)  # taken before reading the XP balance
        price = freeze_price()
        balance = xp_balance(user)
        if balance < price:
            raise InsufficientXP(price, balance)

        XPEvent.objects.create(
            user=user,
            source_type="shop",
            base_points=min(price, 1000),  # base_points_range_constraint
            multiplier=1.0,
            xp_delta=-price,
        )
        return grant_freeze(user, Entry.XP_REDEEM, xp_spent=price)


def cover_missed_days(profile: StreakProfile, activity_date: date) -> bool:
    """
    Spend tokens on the days between ``last_activity_date`` and ``activity_date``.

    Returns True when every missed day is protected, either now or by an earlier
    run. Tokens are only spent if all of the remaining days can be paid for.

    ``profile`` must be locked by the caller. ``profile.streak_freezes`` is
    changed in memory and the caller saves it.
    """
    last = profile.last_activity_date
    if last is None:
        return True
    gap = (activity_date - last).days - 1
    if gap <= 0:
        return True

    covered = set(
        StreakFreezeLedger.objects.filter(
            user_id=profile.user_id,
            protected_date__gt=last,
            protected_date__lt=activity_date,
        ).values_list("protected_date", flat=True)
    )
    needed = gap - len(covered)
    if needed > profile.streak_freezes:
        return False
    if needed == 0:
        return True

    for offset in range(1, gap + 1):
        day = last + timedelta(days=offset)
        if day in covered:
            continue
        profile.streak_freezes -= 1
        StreakFreezeLedger.objects.create(
            user_id=profile.user_id,
            entry_type=Entry.CONSUMED,
            delta=-1,
            balance_after=profile.streak_freezes,
            protected_date=day,
        )
    _bump_inventory(profile.user_id, "total_used", needed)
    logger.info(
        "Used %d streak freeze(s) for user_id=%s, %d left",
        needed,
        profile.user_id,
        profile.streak_freezes,
    )
    return True


def apply_due_freezes() -> int:
    """
    Nightly pass: protect days that have already ended without any activity.

    Runs hourly so each learner is handled shortly after their own midnight.
    Running it again is harmless, a date is only ever charged once. It does not
    reset streaks, that still happens on the next activity.

    Returns the number of tokens spent.
    """
    from apps.progress.streak_engine import get_user_local_date

    # A local calendar date is at most one day ahead of UTC, so anyone who has
    # missed a full day was last active before today's UTC date.
    candidates = list(
        StreakProfile.objects.filter(
            streak_freezes__gt=0,
            current_streak__gt=0,
            last_activity_date__lt=timezone.now().date(),
        ).values_list("pk", flat=True)
    )

    spent = 0
    for pk in candidates:
        try:
            with transaction.atomic():
                profile = (
                    StreakProfile.objects.select_for_update(of=("self",))
                    .select_related("user")
                    .get(pk=pk)
                )
                today = get_user_local_date(profile.user)
                before = profile.streak_freezes
                if not before or not cover_missed_days(profile, today):
                    continue
                if profile.streak_freezes != before:
                    profile.save(update_fields=["streak_freezes", "updated_at"])
                    spent += before - profile.streak_freezes
        except Exception:
            logger.exception("Could not apply streak freezes for profile %s", pk)
    return spent


def weekly_goal_status(user, week_start: date) -> dict:
    """
    Progress of one Monday-to-Sunday week (UTC, same as WeeklyGoal).

    A lesson counts in the week it first earned XP, so replaying an old lesson
    does not count again.
    """
    start = datetime.combine(week_start, time.min, tzinfo=dt_timezone.utc)
    lesson_xp = XPEvent.objects.filter(
        user=user,
        source_type="lesson",
        source_id__isnull=False,
        xp_delta__gt=0,
    ).order_by()
    completed = (
        lesson_xp.filter(
            created_at__gte=start,
            created_at__lt=start + timedelta(days=7),
            source_id__in=LessonProgress.objects.filter(
                user=user, completed=True
            ).values("lesson_id"),
        )
        .exclude(
            source_id__in=lesson_xp.filter(created_at__lt=start).values("source_id")
        )
        .values("source_id")
        .distinct()
        .count()
    )
    chosen = (
        WeeklyGoal.objects.filter(user=user, week_start_date=week_start)
        .values_list("target_lessons", flat=True)
        .first()
    )
    target = max(chosen or MIN_WEEKLY_LESSONS, MIN_WEEKLY_LESSONS)
    claimed = StreakFreezeLedger.objects.filter(
        user=user, week_start=week_start
    ).exists()
    return {
        "week_start": week_start,
        "target_lessons": target,
        "completed_lessons": completed,
        "claimed": claimed,
        "claimable": not claimed and completed >= target,
    }


def recent_weeks(user, today: Optional[date] = None) -> list[dict]:
    """Last week and this week, the two that can still be claimed."""
    today = today or timezone.now().date()
    this_week = today - timedelta(days=today.weekday())
    return [
        weekly_goal_status(user, week)
        for week in (this_week - timedelta(days=7), this_week)
    ]


def claim_weekly_goal_freezes(
    user, today: Optional[date] = None
) -> list[StreakFreezeLedger]:
    """Grant one token for each recent week whose goal is met and unclaimed."""
    with transaction.atomic():
        lock_profile(user)  # a second claim waits here, then sees the ledger rows
        return [
            grant_freeze(user, Entry.WEEKLY_GOAL, week_start=week["week_start"])
            for week in recent_weeks(user, today)
            if week["claimable"]
        ]
