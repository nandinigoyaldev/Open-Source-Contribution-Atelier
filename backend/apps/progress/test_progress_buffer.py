import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.content.models import Lesson
from apps.progress.models import DailyActivity, LessonProgress, StreakProfile, XPEvent
from apps.progress.services.progress_buffer import ProgressBufferService
from apps.progress.tasks import process_buffered_progress_updates

User = get_user_model()


class MockRedisClient:
    def __init__(self):
        self.data = {}
        self.sets = {}

    def set(self, key, value, ex=None):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)

    def sadd(self, key, *values):
        if key not in self.sets:
            self.sets[key] = set()
        for v in values:
            self.sets[key].add(v)

    def spop(self, key, count=1):
        if key not in self.sets or not self.sets[key]:
            return []
        items = list(self.sets[key])[:count]
        self.sets[key] -= set(items)
        return items

    def scard(self, key):
        return len(self.sets.get(key, []))

    def delete(self, *keys):
        for k in keys:
            self.data.pop(k, None)

    def incr(self, key):
        self.data[key] = int(self.data.get(key, 0)) + 1

    def incrby(self, key, amount):
        self.data[key] = int(self.data.get(key, 0)) + amount


class ProgressBufferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpassword123"
        )
        self.lesson = Lesson.objects.create(
            title="Test Lesson",
            slug="test-lesson",
            order=1,
            estimated_minutes=10,
            content="Content",
        )
        self.mock_redis = MockRedisClient()
        self.redis_patcher = patch.object(
            ProgressBufferService, "get_redis_client", return_value=self.mock_redis
        )
        self.redis_patcher.start()

    def tearDown(self):
        self.redis_patcher.stop()

    @patch("apps.progress.services.progress_batch_service.async_task")
    @patch("django.utils.timezone.now")
    def test_buffer_update_and_process(self, now, _queue_badges):
        instant = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
        now.return_value = instant
        payload = {
            "user_id": self.user.id,
            "lesson_slug": self.lesson.slug,
            "score": 100,
            "completed": True,
        }

        buffered = ProgressBufferService.buffer_update(
            self.user.id, self.lesson.slug, payload, activity_type="lesson"
        )
        self.assertTrue(buffered)

        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["queue_size"], 1)

        process_buffered_progress_updates()

        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["queue_size"], 0)
        self.assertEqual(metrics["total_processed"], 1)

        progress = LessonProgress.objects.get(user=self.user, lesson=self.lesson)
        self.assertTrue(progress.completed)
        self.assertEqual(progress.base_score, 100)

        xp_count = XPEvent._default_manager.filter(
            user=self.user, source_id=self.lesson.id
        ).count()
        self.assertEqual(xp_count, 1)
        self.assertEqual(
            DailyActivity._default_manager.get(user=self.user).date, instant.date()
        )
        self.assertEqual(
            StreakProfile._default_manager.get(user=self.user).current_streak, 1
        )

        now.return_value = instant + timedelta(days=1)
        ProgressBufferService.buffer_update(self.user.id, self.lesson.slug, payload)
        process_buffered_progress_updates()
        self.assertEqual(
            DailyActivity._default_manager.filter(user=self.user).count(), 1
        )
        self.assertEqual(XPEvent._default_manager.get(user=self.user).xp_delta, 100)

    def test_debounce_behavior(self):
        payload1 = {
            "user_id": self.user.id,
            "lesson_slug": self.lesson.slug,
            "score": 50,
            "completed": False,
        }
        payload2 = {
            "user_id": self.user.id,
            "lesson_slug": self.lesson.slug,
            "score": 100,
            "completed": True,
        }

        ProgressBufferService.buffer_update(self.user.id, self.lesson.slug, payload1)
        ProgressBufferService.buffer_update(self.user.id, self.lesson.slug, payload2)

        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["queue_size"], 1)

        process_buffered_progress_updates()

        progress = LessonProgress.objects.get(user=self.user, lesson=self.lesson)
        self.assertTrue(progress.completed)
        self.assertEqual(progress.base_score, 100)

    @patch(
        "apps.progress.services.progress_batch_service.process_bulk_progress_updates"
    )
    def test_retry_mechanism(self, mock_process):
        mock_process.side_effect = Exception("Database lock error")

        payload = {
            "user_id": self.user.id,
            "lesson_slug": self.lesson.slug,
            "score": 80,
            "completed": True,
        }

        ProgressBufferService.buffer_update(self.user.id, self.lesson.slug, payload)

        process_buffered_progress_updates()

        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["queue_size"], 0)
        self.assertEqual(metrics["retry_queue_size"], 1)
        self.assertEqual(metrics["total_retries"], 1)

        process_buffered_progress_updates()
        process_buffered_progress_updates()
        process_buffered_progress_updates()

        metrics = ProgressBufferService.get_queue_metrics()
        self.assertEqual(metrics["retry_queue_size"], 0)
        self.assertEqual(metrics["dlq_size"], 1)
        self.assertFalse(DailyActivity._default_manager.filter(user=self.user).exists())
