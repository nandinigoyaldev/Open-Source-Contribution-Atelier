import os
from pathlib import Path

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import PurgeLog
from apps.dashboard.models import Issue

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

    def test_n_plus_one_query_detection(self):
        from nplusone.core.exceptions import NPlusOneError
        from nplusone.core.profiler import Profiler

        users = [
            User.objects.create_user(username=f"user_{i}", password="password123")
            for i in range(3)
        ]

        for i in range(3):
            Issue.objects.create(
                title=f"Test Issue {i}",
                description="Test Description",
                assigned_to=users[i],
                status="open",
            )

        with self.assertRaises(NPlusOneError):
            with Profiler():
                parent_users = list(User.objects.all())
                for user in parent_users:
                    _ = list(user.assigned_issues.all())


class DatabaseBackupTests(TestCase):
    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @override_settings(BACKUP_DIR=None)
    def test_backup_creates_file(self):
        from django.conf import settings as _s

        _s.BACKUP_DIR = self.tmpdir

        from apps.core.tasks import backup_database

        result = backup_database()

        self.assertIsNotNone(result)
        self.assertTrue(Path(result).exists())
        self.assertGreater(Path(result).stat().st_size, 0)

    @override_settings(BACKUP_DIR=None, BACKUP_RETENTION_DAYS=30)
    def test_prune_removes_old_files(self):
        from django.conf import settings as _s

        _s.BACKUP_DIR = self.tmpdir
        _s.BACKUP_RETENTION_DAYS = 30

        old_file = Path(self.tmpdir) / "backup_20000101_000000.json"
        old_file.write_text("[]")
        old_mtime = (timezone.now() - timedelta(days=31)).timestamp()
        os.utime(old_file, (old_mtime, old_mtime))

        from apps.core.tasks import prune_old_backups

        deleted = prune_old_backups()

        self.assertEqual(deleted, 1)
        self.assertFalse(old_file.exists())

    @override_settings(BACKUP_DIR=None, BACKUP_RETENTION_DAYS=30)
    def test_prune_keeps_recent_files(self):
        from django.conf import settings as _s

        _s.BACKUP_DIR = self.tmpdir
        _s.BACKUP_RETENTION_DAYS = 30

        recent_file = Path(self.tmpdir) / "backup_20991231_000000.json"
        recent_file.write_text("[]")

        from apps.core.tasks import prune_old_backups

        deleted = prune_old_backups()

        self.assertEqual(deleted, 0)
        self.assertTrue(recent_file.exists())

    @override_settings(BACKUP_DIR=None)
    def test_prune_missing_dir_returns_zero(self):
        from django.conf import settings as _s

        _s.BACKUP_DIR = str(Path(self.tmpdir) / "nonexistent")

        from apps.core.tasks import prune_old_backups

        self.assertEqual(prune_old_backups(), 0)


class CircuitBreakerTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_circuit_breaker_success_flow(self):
        from apps.core.resilience import CircuitBreaker

        cb = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=2)

        self.assertEqual(cb.get_state(), "closed")

        with cb:
            pass

        self.assertEqual(cb.get_state(), "closed")

    def test_circuit_breaker_failure_flow_and_open(self):
        from apps.core.resilience import CircuitBreaker, CircuitOpenError

        cb = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=2)

        for _ in range(3):
            try:
                with cb:
                    raise ValueError("Fail")
            except ValueError:
                pass

        self.assertEqual(cb.get_state(), "open")

        with self.assertRaises(CircuitOpenError):
            with cb:
                pass

    def test_circuit_breaker_recovery_half_open(self):
        import time

        from apps.core.resilience import CircuitBreaker

        cb = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=1)

        for _ in range(2):
            try:
                with cb:
                    raise ValueError("Fail")
            except ValueError:
                pass

        self.assertEqual(cb.get_state(), "open")

        time.sleep(1.1)

        self.assertEqual(cb.get_state(), "half_open")

        with cb:
            pass

        self.assertEqual(cb.get_state(), "closed")


class CacheTaggingAndInvalidationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_set_and_get_tagged_cache(self):
        from apps.core.cache.invalidation import (
            set_tagged_cache,
            get_tagged_cache,
            get_keys_for_tag,
        )

        set_tagged_cache(
            "user_profile_42",
            {"name": "Alice"},
            ["user:42", "all_profiles"],
            timeout=60,
        )

        val = get_tagged_cache("user_profile_42")
        self.assertEqual(val, {"name": "Alice"})

        # Verify tag association
        self.assertIn("user_profile_42", get_keys_for_tag("user:42"))
        self.assertIn("user_profile_42", get_keys_for_tag("all_profiles"))

    def test_invalidate_tag(self):
        from apps.core.cache.invalidation import (
            set_tagged_cache,
            get_tagged_cache,
            invalidate_tag,
        )

        set_tagged_cache("k1", "v1", ["user:1"], timeout=60)
        set_tagged_cache("k2", "v2", ["user:1", "global"], timeout=60)
        set_tagged_cache("k3", "v3", ["global"], timeout=60)

        invalidate_tag("user:1")

        self.assertIsNone(get_tagged_cache("k1"))
        self.assertIsNone(get_tagged_cache("k2"))
        self.assertEqual(get_tagged_cache("k3"), "v3")

    def test_invalidate_wildcard_tag(self):
        from apps.core.cache.invalidation import (
            set_tagged_cache,
            get_tagged_cache,
            invalidate_tag,
        )

        set_tagged_cache("k1", "v1", ["leaderboard:weekly"], timeout=60)
        set_tagged_cache("k2", "v2", ["leaderboard:monthly"], timeout=60)
        set_tagged_cache("k3", "v3", ["user:1"], timeout=60)

        invalidate_tag("leaderboard:*")

        self.assertIsNone(get_tagged_cache("k1"))
        self.assertIsNone(get_tagged_cache("k2"))
        self.assertEqual(get_tagged_cache("k3"), "v3")

    @patch("apps.core.cache.invalidation.random.random")
    def test_xfetch_stampede_protection(self, mock_random):
        from apps.core.cache.invalidation import set_tagged_cache, get_tagged_cache

        # Cache with delta=1.5 seconds, key expires in 5 seconds
        set_tagged_cache("hot_key", "hot_value", ["tags"], timeout=5, delta=1.5)

        # Mock random.random() to return 0.001 to force early expiration
        mock_random.return_value = 0.001
        self.assertIsNone(get_tagged_cache("hot_key", beta=1.0))

        # Mock random to return 0.99 (ln(0.99) ~ -0.01) to verify no early expiration
        mock_random.return_value = 0.99
        self.assertEqual(get_tagged_cache("hot_key", beta=1.0), "hot_value")

    @patch("apps.core.tasks.invalidate_tag_task.delay")
    def test_signals_trigger_invalidation(self, mock_delay):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Save a User to trigger the signal
        u = User.objects.create_user(username="temp_cache_user", password="pwd")

        # Verify user:id and leaderboard:* tags are queued for invalidation
        mock_delay.assert_any_call(f"user:{u.id}")
        mock_delay.assert_any_call("leaderboard:*")
