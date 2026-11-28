# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOperatorIssue=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.gamification.models import ShopItem
from apps.progress.models import (
    DailyActivity,
    LessonProgress,
    StreakFreezeInventory,
    StreakFreezeLedger,
    StreakProfile,
    StreakRecoveryPlan,
    WeeklyGoal,
    XPEvent,
)
from apps.progress.services import streak_engine as freezes
from apps.progress.services.streak_recovery_service import StreakRecoveryService
from apps.progress.streak_engine import StreakEngine

pytestmark = pytest.mark.django_db

User = get_user_model()
Entry = StreakFreezeLedger.EntryType

# A Wednesday, so "this week" started on 2026-09-07.
TODAY = date(2026, 9, 9)
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=dt_timezone.utc)
LAST_WEEK = date(2026, 8, 31)
THIS_WEEK = date(2026, 9, 7)


@pytest.fixture
def learner():
    return User.objects.create_user(username="freezer", password="pw123456!")


@pytest.fixture
def client(learner):
    api = APIClient()
    api.force_authenticate(user=learner)
    return api


@pytest.fixture
def clock():
    with patch("django.utils.timezone.now", return_value=NOW) as mocked:
        yield mocked


def give_xp(user, amount):
    XPEvent.objects.create(
        user=user, source_type="milestone", base_points=amount, xp_delta=amount
    )


def make_streak(user, *, streak=5, freezes_held=2, last=None):
    profile, _ = StreakProfile.objects.update_or_create(
        user=user,
        defaults={
            "current_streak": streak,
            "longest_streak": streak,
            "streak_freezes": freezes_held,
            "last_activity_date": last or TODAY - timedelta(days=2),
        },
    )
    return profile


def finish_lessons(user, count, when, prefix="lesson"):
    for index in range(count):
        lesson = Lesson.objects.create(
            slug=f"{prefix}-{index}", title=f"{prefix} {index}"
        )
        LessonProgress.objects.bulk_create(
            [LessonProgress(user=user, lesson=lesson, completed=True, score=100)]
        )
        event = XPEvent.objects.create(
            user=user,
            source_type="lesson",
            source_id=lesson.id,
            base_points=100,
            xp_delta=100,
        )
        XPEvent.objects.filter(pk=event.pk).update(created_at=when)


def consumed_dates(user):
    return sorted(
        StreakFreezeLedger.objects.filter(
            user=user, entry_type=Entry.CONSUMED
        ).values_list("protected_date", flat=True)
    )


# -- consumption ----------------------------------------------------------


def test_activity_after_missed_days_consumes_one_freeze_per_day(learner):
    make_streak(learner, freezes_held=3, last=TODAY - timedelta(days=3))

    result = StreakEngine.record_activity(learner, TODAY)

    assert result["current_streak"] == 6
    assert result["streak_freezes"] == 1
    assert consumed_dates(learner) == [
        TODAY - timedelta(days=2),
        TODAY - timedelta(days=1),
    ]
    assert list(
        StreakFreezeLedger.objects.filter(user=learner)
        .order_by("protected_date")
        .values_list("delta", "balance_after")
    ) == [(-1, 2), (-1, 1)]
    assert StreakFreezeInventory.objects.get(user=learner).total_used == 2


def test_daily_activity_path_writes_the_same_ledger(learner):
    make_streak(learner, freezes_held=1)

    _, profile = DailyActivity.log_and_update_streak(user=learner, date=TODAY)

    assert (profile.current_streak, profile.streak_freezes) == (6, 0)
    assert consumed_dates(learner) == [TODAY - timedelta(days=1)]


def test_too_few_freezes_resets_streak_and_spends_nothing(learner):
    make_streak(learner, freezes_held=1, last=TODAY - timedelta(days=4))

    result = StreakEngine.record_activity(learner, TODAY)

    assert (result["current_streak"], result["streak_freezes"]) == (1, 1)
    assert not StreakFreezeLedger.objects.exists()


def test_activity_services_do_not_charge_one_gap_twice(learner):
    make_streak(learner, freezes_held=2)

    StreakEngine.record_activity(learner, TODAY)
    DailyActivity.log_and_update_streak(user=learner, date=TODAY)
    StreakEngine.record_activity(learner, TODAY)

    profile = StreakProfile.objects.get(user=learner)
    assert (profile.current_streak, profile.streak_freezes) == (6, 1)
    assert len(consumed_dates(learner)) == 1


# -- nightly pass ---------------------------------------------------------


def test_nightly_pass_protects_yesterday_once(learner, clock):
    make_streak(learner, freezes_held=2)

    assert freezes.apply_due_freezes() == 1
    assert freezes.apply_due_freezes() == 0

    profile = StreakProfile.objects.get(user=learner)
    assert (profile.current_streak, profile.streak_freezes) == (5, 1)
    assert profile.last_activity_date == TODAY - timedelta(days=2)
    assert consumed_dates(learner) == [TODAY - timedelta(days=1)]


def test_activity_after_nightly_pass_is_not_charged_again(learner, clock):
    make_streak(learner, freezes_held=1)
    freezes.apply_due_freezes()

    result = StreakEngine.record_activity(learner, TODAY)

    assert (result["current_streak"], result["streak_freezes"]) == (6, 0)
    assert len(consumed_dates(learner)) == 1


def test_nightly_passes_over_several_days_then_run_out(learner, clock):
    make_streak(learner, freezes_held=2)

    spent = []
    for offset in range(3):
        clock.return_value = NOW + timedelta(days=offset)
        spent.append(freezes.apply_due_freezes())

    assert spent == [1, 1, 0]
    # The third missed day is unpaid, so coming back starts over.
    result = StreakEngine.record_activity(learner, TODAY + timedelta(days=2))
    assert (result["current_streak"], result["streak_freezes"]) == (1, 0)


def test_nightly_pass_uses_the_learners_own_date(learner, clock):
    # 12:00 UTC on the 9th is already the 10th at UTC+14.
    learner.user_profile.timezone = "Pacific/Kiritimati"
    learner.user_profile.save(update_fields=["timezone"])
    make_streak(learner, freezes_held=1, last=TODAY - timedelta(days=1))

    assert freezes.apply_due_freezes() == 1
    assert consumed_dates(learner) == [TODAY]


@pytest.mark.parametrize(
    "streak,held,days_ago",
    [
        (5, 2, 1),  # active yesterday, nothing missed yet
        (0, 2, 2),  # no streak to protect
        (5, 0, 2),  # no tokens
        (5, 2, 10),  # already broken, more days missed than tokens
    ],
)
def test_nightly_pass_skips_ineligible_learners(learner, clock, streak, held, days_ago):
    make_streak(
        learner,
        streak=streak,
        freezes_held=held,
        last=TODAY - timedelta(days=days_ago),
    )

    assert freezes.apply_due_freezes() == 0
    assert StreakProfile.objects.get(user=learner).streak_freezes == held
    assert not StreakFreezeLedger.objects.exists()


def test_same_date_cannot_be_written_twice(learner):
    row = {
        "user": learner,
        "entry_type": Entry.CONSUMED,
        "delta": -1,
        "balance_after": 0,
        "protected_date": TODAY,
    }
    StreakFreezeLedger.objects.create(**row)

    with pytest.raises(IntegrityError), transaction.atomic():
        StreakFreezeLedger.objects.create(**row)


@pytest.mark.parametrize(
    "spend",
    [
        lambda user: StreakEngine.record_activity(user, TODAY),
        lambda user: DailyActivity.log_and_update_streak(user=user, date=TODAY),
        lambda user: freezes.apply_due_freezes(),
        lambda user: freezes.redeem_with_xp(user),
        lambda user: freezes.claim_weekly_goal_freezes(user, TODAY),
    ],
    ids=["engine", "daily-activity", "nightly", "redeem", "claim"],
)
def test_every_balance_change_locks_the_streak_row(learner, clock, spend):
    # SQLite ignores FOR UPDATE, so check that the lock is asked for.
    make_streak(learner)
    give_xp(learner, 500)
    locked = []
    original = QuerySet.select_for_update

    def record(queryset, *args, **kwargs):
        locked.append(queryset.model)
        return original(queryset, *args, **kwargs)

    with patch.object(QuerySet, "select_for_update", record):
        spend(learner)

    assert StreakProfile in locked


def test_recovery_plan_completion_keeps_the_freeze_balance(learner):
    make_streak(learner, freezes_held=0)
    plan = StreakRecoveryPlan.objects.create(
        user=learner,
        target_date=TODAY,
        previous_streak=5,
        quiz_target=0,
        reading_target=0,
        code_target=0,
    )
    real_get = StreakProfile.objects.get

    def get_then_grant(*args, **kwargs):
        stale = real_get(*args, **kwargs)
        freezes.grant_freeze(learner, Entry.XP_REDEEM)
        return stale

    with patch.object(StreakProfile.objects, "get", side_effect=get_then_grant):
        StreakRecoveryService.sync_and_update_progress(plan)

    profile = real_get(user=learner)
    assert (profile.current_streak, profile.streak_freezes) == (6, 1)


# -- redeeming with XP ----------------------------------------------------


def test_redeem_charges_xp_and_records_it(client, learner):
    give_xp(learner, 400)

    response = client.post("/api/auth/shop/streak-freeze/")

    assert response.status_code == 200
    assert response.data["streak_freezes"] == 1
    assert (response.data["xp_spent"], response.data["remaining_xp"]) == (150, 250)
    entry = StreakFreezeLedger.objects.get(user=learner)
    assert (entry.entry_type, entry.delta, entry.xp_spent) == (Entry.XP_REDEEM, 1, 150)
    assert StreakFreezeInventory.objects.get(user=learner).total_redeemed == 1


def test_redeem_without_enough_xp_changes_nothing(client, learner):
    give_xp(learner, 149)

    response = client.post("/api/auth/shop/streak-freeze/")

    assert response.status_code == 400
    assert "Not enough XP" in response.data["error"]
    assert not StreakFreezeLedger.objects.exists()
    assert freezes.xp_balance(learner) == 149
    assert not StreakProfile.objects.filter(user=learner, streak_freezes__gt=0).exists()


def test_redeem_cannot_spend_the_same_xp_twice(learner):
    give_xp(learner, 200)
    freezes.redeem_with_xp(learner)

    with pytest.raises(freezes.InsufficientXP):
        freezes.redeem_with_xp(learner)

    assert freezes.xp_balance(learner) == 50
    assert StreakProfile.objects.get(user=learner).streak_freezes == 1


def test_redeem_uses_the_shop_price(learner):
    ShopItem.objects.create(
        name="Freeze", description="d", item_type="streak_freeze", cost=300
    )
    give_xp(learner, 299)

    with pytest.raises(freezes.InsufficientXP) as caught:
        freezes.redeem_with_xp(learner)

    assert caught.value.price == 300


def test_shop_purchase_is_written_to_the_ledger(client, learner):
    item = ShopItem.objects.create(
        name="Freeze", description="d", item_type="streak_freeze", cost=100
    )
    give_xp(learner, 100)

    response = client.post(
        "/api/gamification/shop/purchase/", {"item_id": item.id}, format="json"
    )

    assert response.status_code == 200
    entry = StreakFreezeLedger.objects.get(user=learner)
    assert (entry.entry_type, entry.xp_spent, entry.balance_after) == (
        Entry.SHOP_PURCHASE,
        100,
        1,
    )
    assert freezes.xp_balance(learner) == 0


# -- weekly goal ----------------------------------------------------------


def test_claim_grants_one_freeze_for_a_completed_week(learner):
    finish_lessons(learner, 5, NOW)

    first = freezes.claim_weekly_goal_freezes(learner, TODAY)
    second = freezes.claim_weekly_goal_freezes(learner, TODAY)

    assert [entry.week_start for entry in first] == [THIS_WEEK]
    assert second == []
    assert StreakProfile.objects.get(user=learner).streak_freezes == 1
    assert StreakFreezeInventory.objects.get(user=learner).total_earned == 1


def test_last_week_can_still_be_claimed(learner):
    finish_lessons(learner, 5, NOW - timedelta(days=7))

    granted = freezes.claim_weekly_goal_freezes(learner, TODAY)

    assert [entry.week_start for entry in granted] == [LAST_WEEK]


def test_lowering_the_target_does_not_make_the_freeze_cheaper(learner):
    WeeklyGoal.objects.create(user=learner, week_start_date=THIS_WEEK, target_lessons=1)
    finish_lessons(learner, 4, NOW)

    assert freezes.claim_weekly_goal_freezes(learner, TODAY) == []


def test_a_higher_personal_target_is_respected(learner):
    WeeklyGoal.objects.create(user=learner, week_start_date=THIS_WEEK, target_lessons=8)
    finish_lessons(learner, 7, NOW)

    assert freezes.claim_weekly_goal_freezes(learner, TODAY) == []


def test_replayed_lessons_do_not_count_again(learner):
    finish_lessons(learner, 5, NOW - timedelta(days=30))
    for lesson_id in LessonProgress.objects.filter(user=learner).values_list(
        "lesson_id", flat=True
    ):
        XPEvent.objects.create(
            user=learner,
            source_type="lesson",
            source_id=lesson_id,
            base_points=10,
            xp_delta=10,
        )
    XPEvent.objects.filter(user=learner, xp_delta=10).update(created_at=NOW)

    assert freezes.weekly_goal_status(learner, THIS_WEEK)["completed_lessons"] == 0


# -- API ------------------------------------------------------------------


def test_status_endpoint_reports_balance_history_and_weeks(client, learner, clock):
    make_streak(learner, freezes_held=1)
    freezes.apply_due_freezes()
    give_xp(learner, 200)
    finish_lessons(learner, 5, NOW)

    data = client.get("/api/progress/streak/freezes/").data

    assert data["streak_freezes"] == 0
    assert (data["price_xp"], data["xp_balance"]) == (150, 700)
    assert data["last_protected_date"] == "2026-09-08"
    assert (data["total_used"], data["total_earned"]) == (1, 0)
    assert [week["claimable"] for week in data["weeks"]] == [False, True]
    assert data["history"][0]["entry_type"] == "consumed"


def test_status_endpoint_for_a_new_user_creates_nothing(client, learner):
    data = client.get("/api/progress/streak/freezes/").data

    assert data["streak_freezes"] == 0
    assert data["history"] == []
    assert not StreakFreezeInventory.objects.exists()


def test_status_endpoint_only_shows_own_entries(client, learner):
    other = User.objects.create_user(username="other", password="pw123456!")
    freezes.grant_freeze(other, Entry.XP_REDEEM)

    assert client.get("/api/progress/streak/freezes/").data["history"] == []


def test_claim_endpoint(client, learner, clock):
    assert client.post("/api/progress/streak/freezes/claim-weekly/").status_code == 400

    finish_lessons(learner, 5, NOW)
    response = client.post("/api/progress/streak/freezes/claim-weekly/")

    assert response.status_code == 200
    assert response.data["streak_freezes"] == 1


@pytest.mark.parametrize(
    "method,url",
    [
        ("get", "/api/progress/streak/freezes/"),
        ("post", "/api/progress/streak/freezes/claim-weekly/"),
        ("post", "/api/auth/shop/streak-freeze/"),
    ],
)
def test_endpoints_need_a_login(method, url):
    assert getattr(APIClient(), method)(url).status_code in (401, 403)
