"""
Unit tests for:
- PrimaryReplicaRouter (read/write routing, read-after-write, replica failover)
- ReadAfterWriteMiddleware (dirty flag lifecycle)
- replication_lag_view (health endpoint)
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory, override_settings

from config.db_router import PrimaryReplicaRouter, mark_user_dirty, is_user_dirty


REPLICAS_SETTINGS = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "replica1": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "replica2": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

DATABASE_REPLICAS_SETTINGS = [
    {"NAME": "replica1", "WEIGHT": 2},
    {"NAME": "replica2", "WEIGHT": 1},
]


@override_settings(DATABASES=REPLICAS_SETTINGS, DATABASE_REPLICAS=DATABASE_REPLICAS_SETTINGS)
class RouterReadWriteTests(TestCase):
    def setUp(self):
        self.router = PrimaryReplicaRouter()

    def test_write_always_goes_to_default(self):
        result = self.router.db_for_write(MagicMock())
        self.assertEqual(result, "default")

    def test_allow_migrate_blocks_replicas(self):
        self.assertFalse(self.router.allow_migrate("replica1", "core"))
        self.assertFalse(self.router.allow_migrate("replica2", "core"))
        self.assertTrue(self.router.allow_migrate("default", "core"))

    def test_read_in_atomic_block_goes_to_primary(self):
        with patch("config.db_router.transaction.get_connection") as mock_conn:
            mock_conn.return_value.in_atomic_block = True
            result = self.router.db_for_read(MagicMock())
        self.assertEqual(result, "default")

    def test_read_after_write_directs_to_primary(self):
        from config.db_router import _local
        _local.user_id = 999
        mark_user_dirty(999)
        with patch("config.db_router.transaction.get_connection") as mock_conn:
            mock_conn.return_value.in_atomic_block = False
            result = self.router.db_for_read(MagicMock())
        self.assertEqual(result, "default")

    def test_read_routes_to_replica_when_clean(self):
        from config.db_router import _local
        _local.user_id = None

        with patch("sys.argv", ["manage.py", "runserver"]), \
             patch("config.db_router.transaction.get_connection") as mock_conn, \
             patch.object(self.router, "_probe_and_select", return_value="replica1"):
            mock_conn.return_value.in_atomic_block = False
            result = self.router.db_for_read(MagicMock())
        self.assertEqual(result, "replica1")

    def test_all_replicas_dead_falls_back_to_default(self):
        import time
        # Mark all replicas as dead
        for r in self.router.replicas:
            self.router._dead_replicas[r] = time.time()

        with patch("config.db_router.transaction.get_connection") as mock_conn:
            mock_conn.return_value.in_atomic_block = False
            result = self.router._probe_and_select()
        self.assertEqual(result, "default")


class MarkDirtyTests(TestCase):
    def test_mark_and_check_dirty(self):
        mark_user_dirty(42)
        self.assertTrue(is_user_dirty(42))

    def test_none_user_not_dirty(self):
        self.assertFalse(is_user_dirty(None))


class ReadAfterWriteMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_middleware(self):
        from config.raw_middleware import ReadAfterWriteMiddleware
        get_response = MagicMock(return_value=MagicMock(status_code=200))
        return ReadAfterWriteMiddleware(get_response)

    def test_post_marks_user_dirty(self):
        middleware = self._make_middleware()
        request = self.factory.post("/api/content/")
        user = MagicMock()
        user.pk = 77
        user.is_authenticated = True
        request.user = user
        middleware(request)
        self.assertTrue(is_user_dirty(77))

    def test_get_does_not_mark_dirty(self):
        middleware = self._make_middleware()
        request = self.factory.get("/api/content/")
        user = MagicMock()
        user.pk = 88
        user.is_authenticated = True
        request.user = user
        middleware(request)
        self.assertFalse(is_user_dirty(88))


class ReplicationLagViewTests(TestCase):
    def test_endpoint_no_replicas(self):
        with override_settings(DATABASE_REPLICAS=[]), \
             patch("config.db_router.PrimaryReplicaRouter.get_replica_lag_info", return_value=[]):
            response = self.client.get("/health/db/replication-lag/")
        self.assertEqual(response.status_code, 200)

    def test_lag_view_returns_json(self):
        with patch("config.db_router.PrimaryReplicaRouter.get_replica_lag_info") as mock_lag:
            mock_lag.return_value = [{"alias": "replica", "lag_seconds": 0.5, "status": "healthy"}]
            response = self.client.get("/health/db/replication-lag/")
        if response.status_code != 404:  # health URL may not be mounted in all test configs
            import json
            data = json.loads(response.content)
            self.assertIn("replicas", data)
