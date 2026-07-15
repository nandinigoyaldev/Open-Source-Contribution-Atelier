from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from apps.core.models import PurgeLog
from apps.dashboard.models import Issue
from django.contrib.auth import get_user_model
from django.core.cache import caches

from unittest.mock import patch

User = get_user_model()


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-default",
        },
        "l1_memory": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-l1",
        },
    }
)
class MultiLevelCacheTests(TestCase):
    def setUp(self):
        from apps.core.cache import MultiLevelCache
        self.cache = MultiLevelCache()
        caches["default"].clear()
        caches["l1_memory"].clear()

    def test_cache_miss_returns_default(self):
        result = self.cache.get("nonexistent", default="fallback")
        self.assertEqual(result, "fallback")

    def test_l2_hit_backfills_l1(self):
        caches["default"].set("key1", "from-redis", timeout=300)
        result = self.cache.get("key1")
        self.assertEqual(result, "from-redis")
        self.assertEqual(caches["l1_memory"].get("key1"), "from-redis")

    def test_l1_hit_avoids_l2(self):
        caches["l1_memory"].set("key2", "from-memory", timeout=300)
        caches["default"].set("key2", "should-not-be-returned", timeout=300)
        result = self.cache.get("key2")
        self.assertEqual(result, "from-memory")

    def test_set_populates_both_levels(self):
        self.cache.set("key3", "value3", timeout=300)
        self.assertEqual(caches["l1_memory"].get("key3"), "value3")
        self.assertEqual(caches["default"].get("key3"), "value3")

    def test_l1_ttl_capped_at_60(self):
        self.cache.set("key4", "value4", timeout=999)
        self.assertIsNotNone(caches["l1_memory"].get("key4"))

    def test_l1_ttl_respects_short_timeout(self):
        self.cache.set("key5", "value5", timeout=30)
        self.assertIsNotNone(caches["l1_memory"].get("key5"))


class SoftDeleteFrameworkTests(TestCase):
    def setUp(self):
        patcher = patch("apps.events.services.event_bus.EventBus.emit")
        self.mock_emit = patcher.start()
        self.addCleanup(patcher.stop)

        self.user = User.objects.create_user(
            username="testuser", password="testpassword"
        )
        self.issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            assigned_to=self.user,
            status="open",
        )

    def test_soft_delete(self):
        self.assertIsNone(self.issue.deleted_at)
        self.assertEqual(Issue.objects.count(), 1)
        self.assertEqual(Issue.all_objects.count(), 1)

        self.issue.delete()
        self.issue.refresh_from_db()

        self.assertIsNotNone(self.issue.deleted_at)
        self.assertEqual(Issue.objects.count(), 0)
        self.assertEqual(Issue.deleted_objects.count(), 1)
        self.assertEqual(Issue.all_objects.count(), 1)

    def test_restore(self):
        self.issue.delete()
        self.assertEqual(Issue.objects.count(), 0)

        self.issue.restore()
        self.issue.refresh_from_db()

        self.assertIsNone(self.issue.deleted_at)
        self.assertEqual(Issue.objects.count(), 1)

    def test_hard_delete(self):
        self.issue.hard_delete()
        self.assertEqual(Issue.all_objects.count(), 0)

    def test_purge_expired_records(self):
        # Soft delete the issue
        self.issue.delete()
        self.assertEqual(Issue.deleted_objects.count(), 1)

        # Update deleted_at to be 31 days ago to simulate expiration
        old_date = timezone.now() - timedelta(days=31)
        Issue.deleted_objects.filter(pk=self.issue.pk).update(deleted_at=old_date)

        from apps.core.tasks import purge_expired_soft_deleted_records

        purge_expired_soft_deleted_records(retention_days=30)

        # The issue should be permanently deleted
        self.assertEqual(Issue.all_objects.count(), 0)

        # Verify PurgeLog was created
        log = PurgeLog.objects.filter(model_name="Issue").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.records_deleted, 1)

    def test_purge_ignores_recent_records(self):
        self.issue.delete()
        self.assertEqual(Issue.deleted_objects.count(), 1)

        # Update deleted_at to 10 days ago (less than retention_days)
        recent_date = timezone.now() - timedelta(days=10)
        Issue.deleted_objects.filter(pk=self.issue.pk).update(deleted_at=recent_date)

        from apps.core.tasks import purge_expired_soft_deleted_records

        purge_expired_soft_deleted_records(retention_days=30)

        # Issue should NOT be deleted
        self.assertEqual(Issue.all_objects.count(), 1)
        self.assertEqual(Issue.deleted_objects.count(), 1)
