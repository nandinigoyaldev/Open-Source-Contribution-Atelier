from unittest.mock import MagicMock, patch

import pytest
from config.db_router import PrimaryReplicaRouter
from django.conf import settings
from django.db import transaction
from django.db.utils import OperationalError


class TestPrimaryReplicaRouter:
    @pytest.fixture(autouse=True)
    def setup_router(self):
        # We need to temporarily remove 'pytest' from sys.argv for the router tests
        # because the router normally forces 'default' db during tests.
        with patch("sys.argv", ["manage.py", "runserver"]):
            self.router = PrimaryReplicaRouter()
            yield

    def test_init_finds_replicas(self):
        with patch.object(
            settings,
            "DATABASES",
            {"default": {}, "replica_1": {}, "replica_2": {}, "other": {}},
        ):
            router = PrimaryReplicaRouter()
            assert set(router.replicas) == {"replica_1", "replica_2"}

    def test_db_for_write_always_default(self):
        assert self.router.db_for_write(None) == "default"

    @patch("config.db_router.connections")
    def test_db_for_read_routes_to_replica(self, mock_connections):
        # Mock connection to return as healthy
        mock_conn = MagicMock()
        mock_conn.connection = True
        mock_connections.__getitem__.return_value = mock_conn

        with patch.object(self.router, "replicas", ["replica_1"]):
            db = self.router.db_for_read(None)
            assert db == "replica_1"

    @patch("config.db_router.connections")
    def test_multiple_replicas_load_balancing(self, mock_connections):
        mock_conn = MagicMock()
        mock_conn.connection = True
        mock_connections.__getitem__.return_value = mock_conn

        with patch.object(self.router, "replicas", ["replica_1", "replica_2"]):
            # It should return one of the replicas
            db = self.router.db_for_read(None)
            assert db in ["replica_1", "replica_2"]

    @patch("config.db_router.transaction.get_connection")
    def test_transaction_aware_routing(self, mock_get_connection):
        # Mock active transaction
        mock_conn = MagicMock()
        mock_conn.in_atomic_block = True
        mock_get_connection.return_value = mock_conn

        with patch.object(self.router, "replicas", ["replica"]):
            # During write transaction, read should go to default
            db = self.router.db_for_read(None)
            assert db == "default"
            mock_get_connection.assert_called_with("default")

    @patch("config.db_router.connections")
    def test_graceful_fallback_when_replica_unhealthy(self, mock_connections):
        # Mock connection to raise OperationalError
        mock_conn = MagicMock()
        mock_conn.connection = None
        mock_conn.ensure_connection.side_effect = OperationalError("DB is down")
        mock_connections.__getitem__.return_value = mock_conn

        with patch.object(self.router, "replicas", ["replica"]):
            db = self.router.db_for_read(None)
            assert db == "default"
            # Verify the replica was marked as dead
            assert "replica" in self.router._dead_replicas

    @patch("config.db_router.time.time")
    @patch("config.db_router.connections")
    def test_dead_replica_retry_after_timeout(self, mock_connections, mock_time):
        mock_time.return_value = 1000.0
        mock_conn = MagicMock()
        mock_conn.connection = True
        mock_connections.__getitem__.return_value = mock_conn

        with patch.object(self.router, "replicas", ["replica"]):
            # Mark replica as dead at time 900.0 (100 seconds ago, > 60s timeout)
            self.router._dead_replicas["replica"] = 900.0
            db = self.router.db_for_read(None)

            # Should have retried and succeeded
            assert db == "replica"
            assert "replica" not in self.router._dead_replicas

    def test_allow_relation(self):
        class MockObj:
            class State:
                db = "default"

            _state = State()

        obj1 = MockObj()
        obj2 = MockObj()

        with patch.object(self.router, "replicas", ["replica"]):
            # Both on default
            assert self.router.allow_relation(obj1, obj2) is True

            # One on default, one on replica
            obj2._state.db = "replica"
            assert self.router.allow_relation(obj1, obj2) is True

            # One on an unknown DB
            obj2._state.db = "other_db"
            assert self.router.allow_relation(obj1, obj2) is None

    def test_allow_migrate(self):
        with patch.object(self.router, "replicas", ["replica"]):
            assert self.router.allow_migrate("replica", "auth") is False
            assert self.router.allow_migrate("replica_2", "auth") is False
            assert self.router.allow_migrate("default", "auth") is True
