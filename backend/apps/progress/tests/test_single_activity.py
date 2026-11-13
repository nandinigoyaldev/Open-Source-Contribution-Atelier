"""Regression coverage for single-completion streak updates (#3370)."""

from datetime import datetime, timedelta, timezone

import pytest
from django.core.cache import cache
from django.db.models import Sum
from django.urls import reverse

from apps.content.models import Exercise, Lesson
from apps.progress.models import (
    DailyActivity,
    ExerciseAttempt,
    LessonProgress,
    LessonProgressSync,
    StreakProfile,
    XPEvent,
)
from apps.progress.services.progress_tracking_service import ProgressTrackingService

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def clock(monkeypatch):
    current = [NOW]
    monkeypatch.setattr("django.utils.timezone.now", lambda: current[0])
    monkeypatch.setattr(
        "apps.progress.services.progress_tracking_service.async_task",
        lambda *args: None,
    )

    def set_time(value):
        current[0] = value

    return set_time


@pytest.fixture
def lessons():
    return [
        Lesson.objects.create(slug=f"single-activity-{index}", title=f"Lesson {index}")
        for index in range(3)
    ]


@pytest.fixture(params=["service", "http"])
def complete(request, user, api_client, clock):
    api_client.force_authenticate(user)

    def submit(lesson, **fields):
        if request.param == "service":
            progress, _, _ = ProgressTrackingService.record_lesson_progress(
                user, lesson.slug, **fields
            )
        else:
            payload = {"lesson_slug": lesson.slug, **fields}
            if "base_score" in payload:
                payload["score"] = payload.pop("base_score")
            exists = LessonProgress.objects.filter(user=user, lesson=lesson).exists()
            response = api_client.post(reverse("my-progress"), payload, format="json")
            assert response.status_code == (200 if exists else 201)
            progress = LessonProgress.objects.get(user=user, lesson=lesson)
            assert response.data["id"] == progress.pk
            assert response.data["lesson_slug"] == lesson.slug
            assert response.data["completed"] == progress.completed
            assert response.data["score"] == progress.score
            assert response.data["version"] == progress.version
        return progress

    return submit


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    ("days_between", "freezes", "current", "remaining"),
    [(1, 0, 2, 0), (2, 1, 2, 0), (2, 0, 1, 0), (3, 1, 1, 1)],
)
def test_single_completion_uses_daily_streak_rules(
    user, lessons, clock, complete, existing, days_between, freezes, current, remaining
):
    complete(lessons[0], base_score=100)
    streak = StreakProfile._default_manager.get(user=user)
    assert streak.current_streak == streak.longest_streak == 1
    StreakProfile._default_manager.filter(user=user).update(streak_freezes=freezes)
    if existing:
        complete(lessons[1], completed=False, base_score=0)

    clock(NOW + timedelta(days=days_between))
    progress = complete(lessons[1], base_score=100)

    streak.refresh_from_db()
    assert (
        streak.current_streak,
        streak.longest_streak,
        streak.streak_freezes,
    ) == (current, current, remaining)
    assert streak.last_activity_date == (NOW + timedelta(days=days_between)).date()
    assert list(
        DailyActivity._default_manager.filter(user=user)
        .order_by("date")
        .values_list("date", flat=True)
    ) == [NOW.date(), streak.last_activity_date]
    assert progress.completed
    assert (
        XPEvent._default_manager.filter(user=user).aggregate(total=Sum("xp_delta"))[
            "total"
        ]
        == 200
    )


def test_same_day_completions_and_retries_count_once(user, lessons, complete):
    complete(lessons[0], idempotency_key="first")
    complete(lessons[1])
    complete(lessons[0], idempotency_key="first")
    complete(lessons[1])

    streak = StreakProfile._default_manager.get(user=user)
    assert streak.current_streak == streak.longest_streak == 1
    assert DailyActivity._default_manager.filter(user=user).count() == 1
    assert XPEvent._default_manager.filter(user=user).count() == 2
    assert LessonProgressSync.objects.filter(user=user).count() == 1


@pytest.mark.parametrize("idempotency_key", [None, "first"])
def test_next_day_retry_does_not_create_activity(
    user, lessons, clock, complete, idempotency_key
):
    complete(lessons[0], idempotency_key=idempotency_key)
    clock(NOW + timedelta(days=1))
    complete(lessons[0], idempotency_key=idempotency_key)

    streak = StreakProfile._default_manager.get(user=user)
    assert streak.current_streak == streak.longest_streak == 1
    assert streak.last_activity_date == NOW.date()
    assert DailyActivity._default_manager.filter(user=user).count() == 1
    assert XPEvent._default_manager.filter(user=user).count() == 1


def test_single_completion_crosses_learner_midnight(user, lessons, clock, complete):
    profile = user.user_profile
    profile.timezone = "Asia/Kolkata"
    profile.save(update_fields=["timezone"])
    clock(NOW.replace(hour=18, minute=29))
    complete(lessons[0])
    clock(NOW.replace(hour=18, minute=31))
    complete(lessons[1])

    streak = StreakProfile._default_manager.get(user=user)
    assert streak.current_streak == streak.longest_streak == 2
    assert streak.last_activity_date == (NOW + timedelta(days=1)).date()
    assert DailyActivity._default_manager.filter(user=user).count() == 2


def test_failed_single_completion_rolls_back_streak_and_freeze(
    user, lessons, clock, monkeypatch
):
    ProgressTrackingService.record_lesson_progress(user, lessons[0].slug)
    StreakProfile._default_manager.filter(user=user).update(streak_freezes=1)
    clock(NOW + timedelta(days=2))

    def fail_xp_write(**kwargs):
        raise RuntimeError("XP write failed")

    monkeypatch.setattr(XPEvent._default_manager, "create", fail_xp_write)
    with pytest.raises(RuntimeError, match="XP write failed"):
        ProgressTrackingService.record_lesson_progress(
            user, lessons[1].slug, idempotency_key="failed"
        )

    streak = StreakProfile._default_manager.get(user=user)
    assert (streak.current_streak, streak.longest_streak, streak.streak_freezes) == (
        1,
        1,
        1,
    )
    assert streak.last_activity_date == NOW.date()
    assert DailyActivity._default_manager.filter(user=user).count() == 1
    assert LessonProgress.objects.filter(user=user).count() == 1
    assert XPEvent._default_manager.filter(user=user).count() == 1
    assert not LessonProgressSync.objects.filter(user=user).exists()


@pytest.mark.parametrize("source", ["lesson", "exercise"])
def test_direct_signal_completion_and_service_share_activity(
    user, lessons, clock, source
):
    if source == "lesson":
        LessonProgress.objects.create(user=user, lesson=lessons[0], completed=True)
    else:
        exercise = Exercise.objects.create(
            lesson=lessons[0],
            title="Streak exercise",
            prompt="Check the working tree",
            expected_command="git status",
        )
        ExerciseAttempt.objects.create(user=user, exercise=exercise, is_correct=False)
        assert not DailyActivity._default_manager.filter(user=user).exists()
        ExerciseAttempt.objects.create(user=user, exercise=exercise, is_correct=True)

    streak = StreakProfile._default_manager.get(user=user)
    assert streak.current_streak == 1
    assert DailyActivity._default_manager.get(user=user).activity_type == source
    ProgressTrackingService.record_lesson_progress(user, lessons[1].slug)
    streak.refresh_from_db()
    assert streak.current_streak == streak.longest_streak == 1
    assert DailyActivity._default_manager.filter(user=user).count() == 1


def test_existing_profile_without_ledger_keeps_same_day_streak(user, lessons, clock):
    StreakProfile._default_manager.update_or_create(
        user=user,
        defaults={
            "current_streak": 5,
            "longest_streak": 8,
            "last_activity_date": NOW.date(),
        },
    )
    ProgressTrackingService.record_lesson_progress(user, lessons[0].slug)
    streak = StreakProfile._default_manager.get(user=user)
    assert (streak.current_streak, streak.longest_streak) == (5, 8)
    assert DailyActivity._default_manager.get(user=user).date == NOW.date()
