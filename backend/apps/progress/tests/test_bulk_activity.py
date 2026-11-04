from datetime import date, datetime, timedelta, timezone

import pytest
from django.urls import reverse

from apps.content.models import Lesson
from apps.progress.models import DailyActivity, LessonProgress, StreakProfile, XPEvent
from apps.progress.services.progress_batch_service import (
    DuplicateEntryException,
    InvalidLessonException,
    process_bulk_progress_updates,
)
from apps.progress.services.progress_tracking_service import ProgressTrackingService

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 8, 19, 20, tzinfo=timezone.utc)


@pytest.fixture
def submit(user, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.now", lambda: NOW)
    monkeypatch.setattr(
        "apps.progress.services.progress_batch_service.async_task",
        lambda *args: None,
    )

    def submit_batch(*items):
        return process_bulk_progress_updates(user, items)

    return submit_batch


@pytest.fixture
def lesson():
    return Lesson.objects.create(slug="bulk-activity", title="Bulk activity")


def test_single_completion_control(user, lesson, submit):
    ProgressTrackingService.record_lesson_progress(user, lesson.slug, base_score=100)
    assert DailyActivity._default_manager.get(user=user).date == NOW.date()
    assert StreakProfile._default_manager.get(user=user).current_streak == 1
    assert XPEvent._default_manager.get(user=user).xp_delta == 100


@pytest.mark.parametrize("existing", [False, True])
def test_http_completion_records_learner_local_activity(
    user, user_b, api_client, lesson, submit, existing
):
    profile = user.user_profile
    profile.timezone = "Asia/Kolkata"
    profile.save(update_fields=["timezone"])
    if existing:
        submit({"lesson_slug": lesson.slug, "completed": False, "score": 0})
        assert not DailyActivity._default_manager.filter(user=user).exists()
    api_client.force_authenticate(user)
    response = api_client.post(
        reverse("bulk-update"),
        {"lessons": [{"lesson_slug": lesson.slug, "completed": True, "score": 100}]},
        format="json",
    )
    assert response.status_code == 200
    progress = LessonProgress.objects.get(user=user, lesson=lesson)
    assert response.data == {
        "success": True,
        "transaction_outcome": "committed",
        "validation_failures": {},
        "updated_count": 1,
        "updated_ids": [progress.pk],
        "versions": {lesson.slug: progress.version},
        "conflicts": [],
        "metadata": {"synced_at": None},
    }
    assert progress.completed
    assert XPEvent._default_manager.get(user=user).xp_delta == 100
    activity = DailyActivity._default_manager.get(user=user)
    assert activity.date == date(2026, 8, 20)
    assert activity.activity_type == "lesson"
    streak = StreakProfile._default_manager.get(user=user)
    assert streak.current_streak == streak.longest_streak == 1
    assert not DailyActivity._default_manager.filter(user=user_b).exists()
    assert not XPEvent._default_manager.filter(user=user_b).exists()


def test_completions_on_one_day_and_later_replay(user, lesson, submit, monkeypatch):
    other = Lesson.objects.create(slug="other-completion", title="Other completion")
    item = {"lesson_slug": lesson.slug, "score": 100}
    initial = submit(item, {"lesson_slug": other.slug, "score": 100})
    assert len(initial.updated_ids) == 2
    assert submit(item).updated_ids == []
    monkeypatch.setattr("django.utils.timezone.now", lambda: NOW + timedelta(days=1))
    replay = submit(item)
    assert replay.updated_ids == []
    assert replay.conflicts == []
    version = initial.versions[lesson.slug]
    correction = submit({**item, "score": 90, "expected_version": version})
    assert len(correction.updated_ids) == 1
    stale = submit({**item, "completed": False, "expected_version": version})
    assert stale.updated_ids == []
    assert stale.conflicts[0]["code"] == "progress_version_conflict"
    assert DailyActivity._default_manager.filter(user=user).count() == 1
    assert StreakProfile._default_manager.get(user=user).current_streak == 1
    assert sorted(
        XPEvent._default_manager.filter(user=user).values_list("xp_delta", flat=True)
    ) == [
        -10,
        100,
        100,
    ]


def test_failed_batch_rolls_back_completion_activity(user, lesson, submit, monkeypatch):
    def fail_after_writes(*args):
        assert LessonProgress.objects.get(user=user, lesson=lesson).completed
        assert XPEvent._default_manager.get(user=user).xp_delta == 100
        assert DailyActivity._default_manager.filter(user=user).exists()
        assert StreakProfile._default_manager.get(user=user).current_streak == 1
        raise RuntimeError("badge dispatch failed")

    monkeypatch.setattr(
        "apps.progress.services.progress_batch_service.async_task", fail_after_writes
    )
    with pytest.raises(RuntimeError, match="badge dispatch failed"):
        submit({"lesson_slug": lesson.slug})
    assert not LessonProgress.objects.filter(user=user).exists()
    assert not XPEvent._default_manager.filter(user=user).exists()
    assert not DailyActivity._default_manager.filter(user=user).exists()
    assert not StreakProfile._default_manager.filter(
        user=user, current_streak__gt=0
    ).exists()


def test_incomplete_and_stale_completion_record_no_activity(user, lesson, submit):
    item = {"lesson_slug": lesson.slug, "completed": False, "score": 0}
    initial = submit(item)
    assert len(initial.updated_ids) == 1
    assert len(submit({**item, "score": 10}).updated_ids) == 1
    stale = submit(
        {**item, "completed": True, "expected_version": initial.versions[lesson.slug]}
    )
    assert stale.updated_ids == []
    assert stale.conflicts[0]["code"] == "progress_version_conflict"
    progress = LessonProgress.objects.get(user=user, lesson=lesson)
    assert (progress.completed, progress.score) == (False, 10)
    assert XPEvent._default_manager.get(user=user).xp_delta == 10
    assert not DailyActivity._default_manager.filter(user=user).exists()
    assert not StreakProfile._default_manager.filter(
        user=user, current_streak__gt=0
    ).exists()


@pytest.mark.parametrize("duplicate", [False, True])
def test_rejected_batch_records_no_activity(user, lesson, submit, duplicate):
    item = {"lesson_slug": lesson.slug}
    second = item if duplicate else {"lesson_slug": "missing-lesson"}
    error = DuplicateEntryException if duplicate else InvalidLessonException
    with pytest.raises(error):
        submit(item, second)
    assert not LessonProgress.objects.filter(user=user).exists()
    assert not XPEvent._default_manager.filter(user=user).exists()
    assert not DailyActivity._default_manager.filter(user=user).exists()
    assert not StreakProfile._default_manager.filter(
        user=user, current_streak__gt=0
    ).exists()


@pytest.mark.parametrize(
    ("days_between", "freezes", "current", "longest"),
    [(1, 0, 3, 3), (2, 1, 3, 3), (2, 0, 1, 2)],
)
def test_bulk_uses_existing_streak_rules(
    user, lesson, submit, days_between, freezes, current, longest
):
    for days_ago in (days_between + 1, days_between):
        DailyActivity.log_and_update_streak(
            user=user, date=NOW.date() - timedelta(days=days_ago)
        )
    StreakProfile._default_manager.filter(user=user).update(streak_freezes=freezes)
    submit({"lesson_slug": lesson.slug})
    streak = StreakProfile._default_manager.get(user=user)
    assert streak.last_activity_date == NOW.date()
    assert (streak.current_streak, streak.longest_streak, streak.streak_freezes) == (
        current,
        longest,
        0,
    )
