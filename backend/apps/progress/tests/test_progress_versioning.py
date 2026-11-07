"""
Lost update tests for lesson progress writes (issue #3319).

Most of this file is deterministic interleaving: two clients read the same row, one
writes, then the other writes with what it saw. That is what a real race looks like
once the row lock has put the two requests in order, and it runs on any database.

ConcurrentRequestTests at the bottom are real threads and need a database where the
second writer has to wait, see writers_wait_for_each_other().
"""

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any, Callable
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, close_old_connections, connection
from django.db.models import QuerySet, Sum
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.content.models import Lesson
from apps.organizations.models import Organization
from apps.progress.models import (
    LessonProgress,
    LessonProgressSync,
    XPEvent,
    XPMultiplierEvent,
)
from apps.progress.services import progress_batch_service
from apps.progress.services.progress_buffer import ProgressBufferService
from apps.progress.services.progress_versioning import VERSION_CONFLICT_CODE
from apps.progress.tasks import process_buffered_progress_updates
from apps.progress.test_progress_buffer import MockRedisClient
from apps.progress.views import BulkProgressUpdateView, MyProgressView

User: Any = get_user_model()
Progress: Any = LessonProgress._default_manager
Sync: Any = LessonProgressSync._default_manager
XP: Any = XPEvent._default_manager
Lessons: Any = Lesson._default_manager


def make_lesson(slug: str) -> Any:
    return Lessons.create(slug=slug, title=slug, difficulty="beginner")


class VersioningTestCase(TestCase):
    def setUp(self) -> None:
        # Throttle counters live in the cache and user ids repeat across tests
        cache.clear()
        self.user = User.objects.create_user(username="learner", password="pw12345!")
        self.lesson = make_lesson("versioned-lesson")
        self.client: Any = APIClient()
        self.client.force_authenticate(user=self.user)

    def write(self, **body: Any) -> Any:
        body.setdefault("lesson_slug", self.lesson.slug)
        return self.client.post(reverse("my-progress"), body, format="json")

    def row(self, lesson: Any = None) -> Any:
        return Progress.get(user=self.user, lesson=lesson or self.lesson)

    def seed_row(self, lesson: Any = None, **fields: Any) -> Any:
        values: dict[str, Any] = {
            "completed": False,
            "base_score": 50,
            "score": 50,
            "multiplier_applied": 1.0,
        }
        values.update(fields)
        return Progress.create(user=self.user, lesson=lesson or self.lesson, **values)

    def assert_conflict(self, response: Any, version: int) -> None:
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], VERSION_CONFLICT_CODE)
        self.assertEqual(response.data["version"], version)


class CompareAndSwapTests(VersioningTestCase):
    def test_new_row_starts_at_version_one(self) -> None:
        response = self.write(score=100, completed=True, expected_version=0)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["version"], 1)
        self.assertEqual(self.row().version, 1)

    def test_progress_list_exposes_the_version(self) -> None:
        self.seed_row()

        response = self.client.get(reverse("my-progress"))

        self.assertEqual(response.data[0]["version"], 1)

    def test_applied_write_bumps_version_and_timestamp(self) -> None:
        before = self.seed_row()

        response = self.write(score=100, completed=True, expected_version=1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], 2)
        after = self.row()
        self.assertEqual(after.version, 2)
        self.assertGreater(after.updated_at, before.updated_at)

    def test_resending_the_same_state_is_not_a_conflict(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100, version=4)

        response = self.write(score=100, completed=True, expected_version=2)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], 4)
        self.assertEqual(self.row().version, 4)

    def test_stale_tab_cannot_undo_a_finished_lesson(self) -> None:
        self.seed_row()
        seen_by_both = 1

        fresh = self.write(score=100, completed=True, expected_version=seen_by_both)
        self.assertEqual(fresh.status_code, 200)
        finished_at = self.row().updated_at

        stale = self.write(score=50, completed=False, expected_version=seen_by_both)

        self.assert_conflict(stale, version=2)
        self.assertEqual(stale.data["expected_version"], seen_by_both)
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, 100)
        self.assertEqual(row.version, 2)
        self.assertEqual(row.updated_at, finished_at)

    def test_conflict_body_is_the_current_row(self) -> None:
        self.seed_row(completed=True, base_score=90, score=90, version=3)

        response = self.write(score=10, completed=False, expected_version=1)

        self.assert_conflict(response, version=3)
        self.assertTrue(response.data["completed"])
        self.assertEqual(response.data["score"], 90)
        self.assertEqual(response.data["lesson_slug"], self.lesson.slug)
        self.assertIsNotNone(response.data["updated_at"])

    def test_stale_write_is_refused_even_when_the_score_is_higher(self) -> None:
        self.seed_row(completed=True, base_score=70, score=70, version=2)

        response = self.write(score=100, completed=True, expected_version=1)

        self.assert_conflict(response, version=2)
        self.assertEqual(self.row().score, 70)

    def test_client_that_saw_no_row_conflicts_with_one_that_exists(self) -> None:
        self.seed_row(completed=True, base_score=70, score=70)

        response = self.write(score=100, completed=True, expected_version=0)

        self.assert_conflict(response, version=1)

    def test_version_on_a_missing_row_just_creates_it(self) -> None:
        response = self.write(score=80, completed=True, expected_version=7)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.row().version, 1)

    def test_refused_write_gives_no_xp(self) -> None:
        self.seed_row(version=2)

        self.write(score=100, completed=True, expected_version=1)

        self.assertEqual(XP.filter(user=self.user).count(), 0)

    def test_retry_with_the_returned_version_can_overwrite_on_purpose(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100, version=5)

        conflict = self.write(score=40, completed=False, expected_version=1)
        retry = self.write(
            score=40, completed=False, expected_version=conflict.data["version"]
        )

        self.assertEqual(retry.status_code, 200)
        row = self.row()
        self.assertFalse(row.completed)
        self.assertEqual(row.score, 40)
        self.assertEqual(row.version, 6)

    def test_invalid_expected_version_is_a_400(self) -> None:
        self.seed_row()

        for bad in (-1, "abc", True):
            response = self.write(score=100, expected_version=bad)
            self.assertEqual(response.status_code, 400, bad)

        self.assertEqual(self.row().version, 1)

    def test_null_expected_version_means_no_version(self) -> None:
        self.seed_row()

        response = self.write(score=100, completed=True, expected_version=None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.row().version, 2)


class IdempotencyLedgerTests(VersioningTestCase):
    def test_retry_of_an_applied_write_is_not_a_conflict(self) -> None:
        self.seed_row()
        body = dict(
            score=100, completed=True, expected_version=1, idempotency_key="attempt-1"
        )

        self.assertEqual(self.write(**body).status_code, 200)
        # Response got lost, the client sends the exact same request again
        retry = self.write(**body)

        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data["version"], 2)
        self.assertEqual(self.row().version, 2)
        self.assertEqual(XP.filter(user=self.user).count(), 1)

    def test_refused_write_does_not_spend_the_key(self) -> None:
        self.seed_row(version=3)
        key = "attempt-2"

        refused = self.write(
            score=100, completed=True, expected_version=1, idempotency_key=key
        )
        self.assert_conflict(refused, version=3)
        self.assertFalse(Sync.filter(idempotency_key=key).exists())

        retried = self.write(
            score=100, completed=True, expected_version=3, idempotency_key=key
        )

        self.assertEqual(retried.status_code, 200)
        self.assertTrue(self.row().completed)


class WritesWithoutAVersionTests(VersioningTestCase):
    def test_first_write_still_works(self) -> None:
        response = self.write(score=100, completed=True)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.row().version, 1)

    def test_completing_a_lesson_still_works(self) -> None:
        self.seed_row()

        response = self.write(score=100, completed=True)

        self.assertEqual(response.status_code, 200)
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, 100)
        self.assertEqual(row.version, 2)

    def test_higher_score_still_works(self) -> None:
        self.seed_row(completed=True, base_score=50, score=50)

        response = self.write(score=90, completed=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.row().score, 90)

    def test_same_state_is_still_a_plain_200(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100)

        response = self.write(score=100, completed=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.row().version, 1)

    def test_cannot_undo_completion(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100)

        response = self.write(score=100, completed=False)

        self.assert_conflict(response, version=1)
        self.assertIsNone(response.data["expected_version"])
        self.assertTrue(self.row().completed)

    def test_cannot_lower_the_score(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100)

        response = self.write(score=30, completed=True)

        self.assert_conflict(response, version=1)
        self.assertEqual(self.row().score, 100)

    def test_completion_is_kept_when_the_score_is_behind(self) -> None:
        self.seed_row(completed=False, base_score=100, score=100)

        response = self.write(score=30, completed=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["completed"])
        self.assertEqual(response.data["score"], 100)
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.base_score, 100)
        self.assertEqual(row.version, 2)

    def test_higher_score_does_not_undo_completion(self) -> None:
        self.seed_row(completed=True, base_score=50, score=50)

        response = self.write(score=90, completed=False)

        self.assertEqual(response.status_code, 200)
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, 90)

    def test_score_is_compared_after_the_multiplier(self) -> None:
        # 100 at double XP is 200, a higher base score at 1x would still drop it
        self.seed_row(base_score=100, multiplier_applied=2.0, score=200)

        response = self.write(score=120, completed=True)

        self.assertEqual(response.status_code, 200)
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, 200)
        self.assertEqual(row.multiplier_applied, 2.0)
        self.assertEqual(XP.filter(user=self.user).count(), 0)

    def test_client_clock_does_not_decide_anything(self) -> None:
        now_ms = int(timezone.now().timestamp() * 1000)
        self.seed_row(completed=True, base_score=100, score=100)

        far_future = self.write(
            score=10, completed=False, client_timestamp=now_ms + 86_400_000
        )
        self.assertEqual(far_future.status_code, 409)

        behind_clock = self.write(
            score=120, completed=True, client_timestamp=now_ms - 86_400_000
        )
        self.assertEqual(behind_clock.status_code, 200)
        self.assertEqual(self.row().score, 120)


class BulkSyncTests(VersioningTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.other = make_lesson("other-lesson")

    def sync(self, *lessons: dict[str, Any]) -> Any:
        return self.client.post(
            reverse("bulk-sync"), {"lessons": list(lessons)}, format="json"
        )

    def test_conflicts_are_per_item_and_the_rest_still_goes_through(self) -> None:
        stale = self.seed_row(completed=True, base_score=100, score=100, version=3)
        fine = self.seed_row(lesson=self.other)

        response = self.sync(
            {
                "lesson_slug": self.lesson.slug,
                "completed": False,
                "score": 1,
                "expected_version": 1,
            },
            {
                "lesson_slug": self.other.slug,
                "completed": True,
                "score": 100,
                "expected_version": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["synced_count"], 1)
        self.assertEqual(response.data["progress_ids"], [fine.id])
        self.assertNotIn(stale.id, response.data["progress_ids"])
        conflict = response.data["conflicts"][0]
        self.assertEqual(conflict["lesson_slug"], self.lesson.slug)
        self.assertEqual(conflict["code"], VERSION_CONFLICT_CODE)
        self.assertEqual(conflict["version"], 3)
        self.assertTrue(conflict["completed"])
        self.assertTrue(self.row().completed)
        self.assertEqual(self.row(self.other).version, 2)

    def test_refused_write_without_a_version_is_not_reported_as_synced(self) -> None:
        row = self.seed_row(completed=True, base_score=100, score=100)

        response = self.sync(
            {"lesson_slug": self.lesson.slug, "completed": False, "score": 100}
        )

        self.assertEqual(response.data["synced_count"], 0)
        self.assertEqual(response.data["progress_ids"], [])
        self.assertEqual(response.data["conflicts"][0]["id"], row.id)

    def test_clean_sync_reports_no_conflicts(self) -> None:
        response = self.sync({"lesson_slug": self.lesson.slug, "score": 100})

        self.assertEqual(response.data["synced_count"], 1)
        self.assertEqual(response.data["conflicts"], [])


class BulkUpdateTests(VersioningTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.other = make_lesson("other-lesson")

    def update(self, *lessons: dict[str, Any]) -> Any:
        return self.client.post(
            reverse("bulk-update"), {"lessons": list(lessons)}, format="json"
        )

    def test_conflicts_are_per_item_and_the_rest_still_commits(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100, version=3)
        self.seed_row(lesson=self.other)

        response = self.update(
            {
                "lesson_slug": self.lesson.slug,
                "completed": False,
                "score": 1,
                "expected_version": 1,
            },
            {
                "lesson_slug": self.other.slug,
                "completed": True,
                "score": 100,
                "expected_version": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["transaction_outcome"], "committed")
        self.assertEqual(response.data["updated_count"], 1)
        self.assertEqual(response.data["versions"], {self.other.slug: 2})
        conflict = response.data["conflicts"][0]
        self.assertEqual(conflict["lesson_slug"], self.lesson.slug)
        self.assertEqual(conflict["version"], 3)
        self.assertEqual(self.row().score, 100)

    def test_applied_write_moves_the_timestamp(self) -> None:
        # bulk_update does not run auto_now, so this used to stay behind
        before = self.seed_row()
        long_ago = before.updated_at - timedelta(days=2)
        Progress.filter(pk=before.pk).update(updated_at=long_ago)

        self.update(
            {
                "lesson_slug": self.lesson.slug,
                "completed": True,
                "score": 100,
                "expected_version": 1,
            }
        )

        row = self.row()
        self.assertEqual(row.version, 2)
        self.assertGreater(row.updated_at, long_ago)

    def test_versions_cover_new_and_unchanged_rows(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100, version=4)

        response = self.update(
            {"lesson_slug": self.lesson.slug, "completed": True, "score": 100},
            {"lesson_slug": self.other.slug, "completed": True, "score": 100},
        )

        self.assertEqual(
            response.data["versions"], {self.lesson.slug: 4, self.other.slug: 1}
        )
        self.assertEqual(response.data["conflicts"], [])

    def test_rows_are_locked_before_they_are_compared(self) -> None:
        self.seed_row()
        real = QuerySet.select_for_update

        with patch.object(
            QuerySet, "select_for_update", autospec=True, side_effect=real
        ) as lock:
            self.update({"lesson_slug": self.lesson.slug, "score": 100})

        self.assertEqual(lock.call_count, 1)
        self.assertIs(lock.call_args.args[0].model, LessonProgress)

    def test_first_write_race_turns_into_a_version_check(self) -> None:
        # Both requests saw no row, the other one committed first
        real_write_batch: Callable[..., Any] = progress_batch_service._write_batch
        calls: list[int] = []

        def lose_the_insert(*args: Any) -> Any:
            calls.append(1)
            if len(calls) == 1:
                self.seed_row(completed=True, base_score=100, score=100)
                raise IntegrityError("unique_user_lesson_progress")
            return real_write_batch(*args)

        with patch.object(progress_batch_service, "_write_batch", lose_the_insert):
            response = self.update(
                {
                    "lesson_slug": self.lesson.slug,
                    "completed": False,
                    "score": 1,
                    "expected_version": 0,
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(calls), 2)
        self.assertEqual(response.data["conflicts"][0]["version"], 1)
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, 100)

    def test_org_member_can_read_back_the_row_it_just_wrote(self) -> None:
        # The client gets its version from this list, so a row missing from it
        # would make every later write look stale
        org: Any = Organization._default_manager.create(name="Org")
        profile: Any = self.user.user_profile
        profile.organization = org
        profile.save()
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))

        self.update({"lesson_slug": self.lesson.slug, "score": 100})

        listed = self.client.get(reverse("my-progress")).data
        self.assertEqual([row["version"] for row in listed], [1])

        self.update(
            {"lesson_slug": self.lesson.slug, "score": 120, "expected_version": 1}
        )

        self.assertEqual(self.row().version, 2)
        self.assertEqual(self.row().organization, org)


class BufferTests(VersioningTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.redis = MockRedisClient()
        patcher = patch.object(
            ProgressBufferService, "get_redis_client", return_value=self.redis
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def queue(self, **payload: Any) -> None:
        payload.update(user_id=self.user.id, lesson_slug=self.lesson.slug)
        ProgressBufferService.buffer_update(self.user.id, self.lesson.slug, payload)

    def test_write_is_not_parked_in_redis(self) -> None:
        response = self.write(score=100, completed=True)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.row().version, 1)
        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["queue_size"], 0)

    def test_stale_write_gets_a_409_with_redis_up(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100, version=2)

        response = self.write(score=10, completed=False, expected_version=1)

        self.assert_conflict(response, version=2)

    def test_flush_cannot_undo_a_finished_lesson(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100)
        self.queue(score=10, completed=False)

        process_buffered_progress_updates()

        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, 100)
        self.assertEqual(row.version, 1)
        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["total_conflicts"], 1)
        # Refused for good, not something to retry
        self.assertEqual(metrics["retry_queue_size"], 0)
        self.assertEqual(metrics["dlq_size"], 0)

    def test_flush_still_applies_a_write_that_moves_forward(self) -> None:
        self.seed_row()
        self.queue(score=100, completed=True)

        process_buffered_progress_updates()

        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.version, 2)
        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["total_conflicts"], 0)


class MultiplierXpTests(VersioningTestCase):
    def test_xp_ledger_follows_the_applied_writes(self) -> None:
        now = timezone.now()
        event: Any = XPMultiplierEvent._default_manager
        event.create(
            name="Double XP",
            multiplier=2.0,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            is_active=True,
        )

        self.write(score=50, completed=True, expected_version=0)
        self.write(score=10, completed=True, expected_version=9)
        self.write(score=60, completed=True, expected_version=1)

        row = self.row()
        total = XP.filter(user=self.user).aggregate(total=Sum("xp_delta"))["total"]
        self.assertEqual(row.score, 120)
        self.assertEqual(total, row.score)


def writers_wait_for_each_other() -> bool:
    """
    A real race only shows anything if the second writer has to wait: row locks on
    PostgreSQL, or SQLite with transaction_mode IMMEDIATE. Plain SQLite ignores
    select_for_update and answers "database is locked", which says nothing about
    this code.
    """
    options = connection.settings_dict.get("OPTIONS") or {}
    return bool(
        connection.features.has_select_for_update
        or options.get("transaction_mode") == "IMMEDIATE"
    )


@unittest.skipUnless(
    writers_wait_for_each_other(), "needs a database where writers wait for each other"
)
class ConcurrentRequestTests(TransactionTestCase):
    WORKERS = 6

    def setUp(self) -> None:
        cache.clear()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="racer", password="pw12345!")
        self.lesson = make_lesson("raced-lesson")
        for target in (
            "apps.progress.services.progress_tracking_service.async_task",
            "apps.progress.services.progress_batch_service.async_task",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, view: Any, path: str, body: dict[str, Any]) -> Any:
        close_old_connections()
        try:
            user = User.objects.get(pk=self.user.pk)
            request = self.factory.post(path, body, format="json")
            force_authenticate(request, user=user)
            return view(request)
        finally:
            close_old_connections()

    def post_progress(self, body: dict[str, Any]) -> Any:
        body = {"lesson_slug": self.lesson.slug, **body}
        return self.request(MyProgressView.as_view(), reverse("my-progress"), body)

    def post_bulk_update(self, item: dict[str, Any]) -> Any:
        body = {"lessons": [{"lesson_slug": self.lesson.slug, **item}]}
        return self.request(
            BulkProgressUpdateView.as_view(), reverse("bulk-update"), body
        )

    def race(self, send: Callable[[Any], Any], bodies: list[dict[str, Any]]) -> list:
        barrier = threading.Barrier(len(bodies))

        def worker(body: dict[str, Any]) -> Any:
            barrier.wait(timeout=30)
            return send(body)

        with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
            return list(pool.map(worker, bodies))

    def row(self) -> Any:
        return Progress.get(user=self.user, lesson=self.lesson)

    def xp_total(self) -> int:
        total = XP.filter(user=self.user).aggregate(total=Sum("xp_delta"))["total"]
        return total or 0

    def seed_row(self, **fields: Any) -> Any:
        return Progress.create(user=self.user, lesson=self.lesson, **fields)

    def test_same_version_exactly_one_write_wins(self) -> None:
        self.seed_row(base_score=5, score=5)
        scores = [10 * (i + 1) for i in range(self.WORKERS)]

        responses = self.race(
            self.post_progress,
            [
                {"score": score, "completed": True, "expected_version": 1}
                for score in scores
            ],
        )

        statuses = sorted(r.status_code for r in responses)
        self.assertEqual(statuses, [200] + [409] * (self.WORKERS - 1))
        winner = next(r for r in responses if r.status_code == 200)
        row = self.row()
        self.assertEqual(row.version, 2)
        self.assertTrue(row.completed)
        self.assertEqual(row.score, winner.data["score"])
        self.assertEqual(self.xp_total(), row.score - 5)
        for response in responses:
            if response.status_code == 409:
                self.assertEqual(response.data["version"], 2)
                self.assertEqual(response.data["score"], row.score)
                self.assertEqual(response.data["updated_at"], winner.data["updated_at"])

    def test_same_version_exactly_one_bulk_update_wins(self) -> None:
        self.seed_row(base_score=5, score=5)

        responses = self.race(
            self.post_bulk_update,
            [
                {"score": 10 * (i + 1), "completed": True, "expected_version": 1}
                for i in range(self.WORKERS)
            ],
        )

        winners = [r for r in responses if not r.data["conflicts"]]
        self.assertEqual(len(winners), 1)
        self.assertTrue(all(r.status_code == 200 for r in responses))
        row = self.row()
        self.assertEqual(row.version, 2)
        for response in responses:
            for conflict in response.data["conflicts"]:
                self.assertEqual(conflict["version"], 2)
                self.assertEqual(conflict["score"], row.score)

    def test_first_write_race_leaves_one_row(self) -> None:
        responses = self.race(
            self.post_progress,
            [
                {"score": 10 * (i + 1), "completed": True, "expected_version": 0}
                for i in range(self.WORKERS)
            ],
        )

        statuses = sorted(r.status_code for r in responses)
        self.assertEqual(statuses, [201] + [409] * (self.WORKERS - 1))
        self.assertEqual(Progress.filter(user=self.user).count(), 1)
        self.assertEqual(self.xp_total(), self.row().score)

    def test_stale_undo_racing_a_higher_score_never_passes_silently(self) -> None:
        self.seed_row(completed=True, base_score=100, score=100)

        undo, raise_score = self.race(
            self.post_progress,
            [
                {"score": 100, "completed": False, "expected_version": 1},
                {"score": 150, "completed": True, "expected_version": 1},
            ],
        )

        # Either order is fine, what matters is that the loser was told
        self.assertEqual(
            sorted([undo.status_code, raise_score.status_code]), [200, 409]
        )
        row = self.row()
        self.assertEqual(row.version, 2)
        if undo.status_code == 409:
            self.assertTrue(row.completed)
            self.assertEqual(row.score, 150)
        else:
            self.assertEqual(raise_score.data["version"], 2)

    def test_writes_without_a_version_end_on_the_best_state(self) -> None:
        self.seed_row(base_score=5, score=5)
        scores = [10 * (i + 1) for i in range(self.WORKERS)]

        responses = self.race(
            self.post_progress,
            [
                {"score": score, "completed": index % 2 == 0}
                for index, score in enumerate(scores)
            ],
        )

        self.assertTrue(all(r.status_code in (200, 409) for r in responses))
        row = self.row()
        self.assertTrue(row.completed)
        self.assertEqual(row.score, max(scores))
        self.assertEqual(row.version, 1 + sum(r.status_code == 200 for r in responses))
        self.assertEqual(self.xp_total(), row.score - 5)
