"""Lag-aware routing, explicit primary pinning and routing metrics (issue #3288)."""

import threading
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from config import db_router_metrics as metrics
from config.db_router import (
    REPLICA_LAG_SQL,
    PrimaryReplicaRouter,
    _local,
    is_primary_pinned,
    is_user_dirty,
    mark_user_dirty,
    use_primary,
)
from config.raw_middleware import ReadAfterWriteMiddleware, resolve_user_id


def connection(lag=0.0, vendor="postgresql", connected=True):
    """A stand-in for a replica connection that reports ``lag`` seconds behind."""
    conn = MagicMock()
    conn.vendor = vendor
    conn.connection = True if connected else None
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (lag,)
    return conn


def fake_connections(**by_alias):
    registry = MagicMock()
    registry.__getitem__.side_effect = lambda alias: by_alias[alias]
    return registry


@pytest.fixture(autouse=True)
def router_env(settings):
    """The router answers 'default' during test runs unless argv says otherwise."""
    metrics.reset()
    cache.clear()
    _local.user_id = None
    _local.primary_pins = 0
    settings.READ_AFTER_WRITE_SECONDS = 5
    settings.REPLICA_MAX_LAG_SECONDS = 5
    settings.REPLICA_LAG_CACHE_SECONDS = 2
    with patch("sys.argv", ["manage.py", "runserver"]):
        yield
    _local.user_id = None
    _local.primary_pins = 0


@pytest.fixture
def router():
    r = PrimaryReplicaRouter()
    r.replicas = ["replica_1"]
    r._weights = {"replica_1": 1}
    return r


class TestLagAwareRouting:
    def test_replica_within_the_limit_serves_reads(self, router):
        with patch(
            "config.db_router.connections",
            fake_connections(replica_1=connection(lag=1.5)),
        ):
            assert router.db_for_read(None) == "replica_1"
        assert metrics.routing_counts() == {"replica:replica": 1}

    def test_lagging_replica_is_skipped_and_the_read_falls_back_to_primary(
        self, router
    ):
        with patch(
            "config.db_router.connections",
            fake_connections(replica_1=connection(lag=12.0)),
        ):
            assert router.db_for_read(None) == "default"
        assert metrics.routing_counts() == {"primary:replica_lagging": 1}

    def test_a_lag_exactly_at_the_limit_is_still_served(self, router):
        with patch(
            "config.db_router.connections",
            fake_connections(replica_1=connection(lag=5.0)),
        ):
            assert router.db_for_read(None) == "replica_1"

    def test_unreadable_lag_is_not_trusted(self, router):
        conn = connection()
        conn.cursor.return_value.__enter__.return_value.execute.side_effect = (
            RuntimeError("boom")
        )
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            assert router.db_for_read(None) == "default"
        assert metrics.routing_counts() == {"primary:replica_lagging": 1}

    def test_the_healthy_replica_is_chosen_over_a_lagging_one(self, router):
        router.replicas = ["slow", "fast"]
        router._weights = {"slow": 1, "fast": 1}
        conns = fake_connections(slow=connection(lag=60), fast=connection(lag=0.2))
        with patch("config.db_router.connections", conns):
            for _ in range(20):
                assert router.db_for_read(None) == "fast"

    def test_a_lagging_replica_is_not_marked_dead_and_comes_back_when_it_catches_up(
        self, router
    ):
        conn = connection(lag=30)
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            with patch("config.db_router.time.monotonic", return_value=100.0):
                assert router.db_for_read(None) == "default"
            assert "replica_1" not in router._dead_replicas

            cursor = conn.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (0.1,)
            with patch(
                "config.db_router.time.monotonic", return_value=103.0
            ):  # past the 2 s cache
                assert router.db_for_read(None) == "replica_1"

    def test_lag_is_cached_between_reads(self, router):
        conn = connection(lag=0.5)
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            with patch("config.db_router.time.monotonic", return_value=50.0):
                for _ in range(10):
                    router.db_for_read(None)
        assert conn.cursor.return_value.__enter__.return_value.execute.call_count == 1

    def test_lag_is_measured_again_after_the_cache_expires(self, router):
        conn = connection(lag=0.5)
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            with patch("config.db_router.time.monotonic", return_value=10.0):
                router.db_for_read(None)
            with patch("config.db_router.time.monotonic", return_value=20.0):
                router.db_for_read(None)
        assert conn.cursor.return_value.__enter__.return_value.execute.call_count == 2

    def test_the_check_can_be_turned_off(self, router, settings):
        settings.REPLICA_MAX_LAG_SECONDS = 0
        conn = connection(lag=999)
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            assert router.db_for_read(None) == "replica_1"
        conn.cursor.assert_not_called()

    def test_backends_without_replication_are_not_checked(self, router):
        conn = connection(lag=999, vendor="sqlite")
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            assert router.db_for_read(None) == "replica_1"
        conn.cursor.assert_not_called()

    def test_default_limit_follows_the_read_after_write_window(self, router, settings):
        del settings.REPLICA_MAX_LAG_SECONDS
        settings.READ_AFTER_WRITE_SECONDS = 3
        assert router._lag_limit() == 3.0

    def test_dedicated_analytics_replica_is_also_lag_checked(self, router):
        from types import SimpleNamespace

        model = SimpleNamespace(
            _meta=SimpleNamespace(app_label="progress", model_name="xpevent")
        )
        with patch.dict(settings.DATABASES, {"read_replica": {}}):
            conns = fake_connections(
                read_replica=connection(lag=40), replica_1=connection(lag=0)
            )
            with patch("config.db_router.connections", conns):
                assert router.db_for_read(model) == "default"
            assert metrics.routing_counts() == {"primary:replica_lagging": 1}

            metrics.reset()
            router._lag_cache.clear()
            conns = fake_connections(
                read_replica=connection(lag=0.3), replica_1=connection(lag=0)
            )
            with patch("config.db_router.connections", conns):
                assert router.db_for_read(model) == "read_replica"

    def test_a_dead_dedicated_replica_is_not_reconnected_on_every_read(self, router):
        from types import SimpleNamespace

        from django.db.utils import OperationalError

        model = SimpleNamespace(
            _meta=SimpleNamespace(app_label="progress", model_name="xpevent")
        )
        conn = connection(connected=False)
        conn.ensure_connection.side_effect = OperationalError("down")
        with patch.dict(settings.DATABASES, {"read_replica": {}}):
            with patch(
                "config.db_router.connections", fake_connections(read_replica=conn)
            ):
                for _ in range(5):
                    assert router.db_for_read(model) == "default"
        assert conn.ensure_connection.call_count == 1
        assert metrics.routing_counts() == {"primary:replica_unavailable": 5}

    def test_lag_sql_reports_zero_for_a_replica_that_has_caught_up(self):
        assert "pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn()" in REPLICA_LAG_SQL
        assert "THEN 0" in REPLICA_LAG_SQL
        assert "pg_last_xact_replay_timestamp" in REPLICA_LAG_SQL

    def test_the_health_view_and_the_router_share_one_lag_query(self, router):
        conn = connection(lag=1.0)
        with patch("config.db_router.connections", fake_connections(replica_1=conn)):
            info = router.get_replica_lag_info()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once_with(REPLICA_LAG_SQL)
        assert info == [{"alias": "replica_1", "lag_seconds": 1.0, "status": "healthy"}]


class TestUsePrimary:
    def test_reads_in_the_block_stay_on_the_primary(self, router):
        with patch(
            "config.db_router.connections", fake_connections(replica_1=connection())
        ):
            assert router.db_for_read(None) == "replica_1"
            with use_primary():
                assert is_primary_pinned()
                assert router.db_for_read(None) == "default"
            assert not is_primary_pinned()
            assert router.db_for_read(None) == "replica_1"
        assert metrics.routing_counts() == {
            "replica:replica": 2,
            "primary:pinned_primary": 1,
        }

    def test_blocks_can_be_nested(self):
        with use_primary():
            with use_primary():
                assert is_primary_pinned()
            assert is_primary_pinned()
        assert not is_primary_pinned()

    def test_the_pin_is_released_when_the_block_raises(self):
        with pytest.raises(ValueError):
            with use_primary():
                raise ValueError("x")
        assert not is_primary_pinned()

    def test_works_as_a_decorator(self, router):
        @use_primary()
        def read():
            return router.db_for_read(None)

        with patch(
            "config.db_router.connections", fake_connections(replica_1=connection())
        ):
            assert read() == "default"
            assert read() == "default"
            assert router.db_for_read(None) == "replica_1"

    def test_the_pin_does_not_leak_into_other_threads(self):
        seen = {}

        def other():
            seen["pinned"] = is_primary_pinned()

        with use_primary():
            t = threading.Thread(target=other)
            t.start()
            t.join()
        assert seen["pinned"] is False

    def test_the_pin_wins_over_everything_else_and_writes_are_unaffected(self, router):
        with use_primary():
            assert router.db_for_write(None) == "default"


class TestRoutingReasons:
    def test_each_reason_is_counted(self, router):
        conns = fake_connections(replica_1=connection())
        with patch("config.db_router.connections", conns):
            router.db_for_read(None)  # replica

            with patch("config.db_router.transaction.get_connection") as get_conn:
                get_conn.return_value.in_atomic_block = True
                router.db_for_read(None)  # atomic block

            _local.user_id = 7
            mark_user_dirty(7)
            router.db_for_read(None)  # read after write
            _local.user_id = None

            router.replicas = []
            router.db_for_read(None)  # nothing configured
        assert metrics.routing_counts() == {
            "replica:replica": 1,
            "primary:atomic_block": 1,
            "primary:read_after_write": 1,
            "primary:no_replica": 1,
        }

    def test_test_runs_are_not_counted(self, router):
        with patch("sys.argv", ["pytest"]):
            assert router.db_for_read(None) == "default"
        assert metrics.routing_counts() == {}

    def test_lag_is_recorded_for_monitoring(self, router):
        with patch(
            "config.db_router.connections",
            fake_connections(replica_1=connection(lag=2.5)),
        ):
            router.db_for_read(None)
        assert metrics.last_lag() == {"replica_1": 2.5}


def request_with(method="GET", token=None, user=None):
    request = getattr(RequestFactory(), method.lower())("/api/progress/me/")
    if token:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if user is not None:
        request.user = user
    return request


def access_token(user_id=42):
    token = AccessToken()
    token["user_id"] = user_id
    return str(token)


class TestReadAfterWriteWithJwt:
    """API clients send a JWT that DRF only checks inside the view."""

    def test_the_user_is_read_from_a_valid_bearer_token(self):
        assert resolve_user_id(request_with(token=access_token(42))) == 42

    def test_a_session_user_still_wins(self):
        user = MagicMock(is_authenticated=True, pk=5)
        assert resolve_user_id(request_with(token=access_token(42), user=user)) == 5

    @pytest.mark.parametrize(
        "header",
        [
            "",
            "Bearer",
            "Bearer ",
            "Bearer not-a-token",
            "Basic abc",
            "Token abc",
            "Bearer a.b.c",
        ],
    )
    def test_anything_else_gives_no_user(self, header):
        request = RequestFactory().get("/")
        request.META["HTTP_AUTHORIZATION"] = header
        assert resolve_user_id(request) is None

    def test_a_token_with_a_bad_signature_is_ignored(self):
        token = access_token(42)
        head, payload, sig = token.split(".")
        forged = ".".join(
            [head, payload, sig[:-4] + ("AAAA" if not sig.endswith("AAAA") else "BBBB")]
        )
        assert resolve_user_id(request_with(token=forged)) is None

    def test_an_expired_token_is_ignored(self):
        token = AccessToken()
        token["user_id"] = 42
        token.set_exp(lifetime=-__import__("datetime").timedelta(minutes=5))
        assert resolve_user_id(request_with(token=str(token))) is None

    def test_a_token_without_a_numeric_user_is_ignored(self):
        token = AccessToken()
        token["user_id"] = "not-a-number"
        assert resolve_user_id(request_with(token=str(token))) is None

    def test_a_write_by_a_jwt_client_pins_their_next_reads_to_the_primary(self, router):
        middleware = ReadAfterWriteMiddleware(
            lambda request: MagicMock(status_code=200)
        )
        middleware(request_with("POST", token=access_token(77)))
        assert is_user_dirty(77)

        # the next request from the same client reads from the primary, not a replica
        seen = {}

        def view(request):
            seen["db"] = router.db_for_read(None)
            return MagicMock(status_code=200)

        with patch(
            "config.db_router.connections", fake_connections(replica_1=connection())
        ):
            ReadAfterWriteMiddleware(view)(request_with("GET", token=access_token(77)))
        assert seen["db"] == "default"

    def test_another_user_still_reads_from_the_replica(self, router):
        mark_user_dirty(77)
        seen = {}

        def view(request):
            seen["db"] = router.db_for_read(None)
            return MagicMock(status_code=200)

        with patch(
            "config.db_router.connections", fake_connections(replica_1=connection())
        ):
            ReadAfterWriteMiddleware(view)(request_with("GET", token=access_token(78)))
        assert seen["db"] == "replica_1"

    def test_a_get_does_not_mark_the_user(self):
        ReadAfterWriteMiddleware(lambda request: MagicMock())(
            request_with("GET", token=access_token(90))
        )
        assert not is_user_dirty(90)

    def test_anonymous_requests_mark_nobody(self):
        ReadAfterWriteMiddleware(lambda request: MagicMock())(request_with("POST"))
        assert _local.user_id is None

    def test_the_thread_local_is_cleared_even_when_the_view_raises(self):
        def boom(request):
            raise RuntimeError("view failed")

        with pytest.raises(RuntimeError):
            ReadAfterWriteMiddleware(boom)(request_with("POST", token=access_token(5)))
        assert _local.user_id is None


@pytest.mark.django_db
def test_a_jwt_api_call_through_the_real_middleware_stack_pins_the_next_reads(
    client, django_user_model
):
    """End to end: a POST with only a bearer token marks that user, a different token does not."""
    user = django_user_model.objects.create_user(
        username="raw-user", password="pw-123456-x"
    )
    other = django_user_model.objects.create_user(
        username="raw-other", password="pw-123456-x"
    )
    token = str(AccessToken.for_user(user))

    client.post(
        "/api/auth/change-password/",
        data={"old_password": "wrong", "new_password": "does-not-matter-1A!"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert is_user_dirty(user.pk)
    assert not is_user_dirty(other.pk)
    assert _local.user_id is None
