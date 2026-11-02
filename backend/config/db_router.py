"""
Weighted round-robin database router with read-after-write consistency,
replica health monitoring, and graceful fallback.

Reads from this router go to healthy replicas using weighted selection.
After any write, the current user's reads are served from primary for
READ_AFTER_WRITE_SECONDS (configurable) to prevent stale reads.
"""

import logging
import random
import sys
import threading
import time
from contextlib import ContextDecorator
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db import connections, transaction
from django.db.utils import OperationalError

from config import db_router_metrics as metrics

logger = logging.getLogger(__name__)

# Thread-local storage for per-request write tracking
_local = threading.local()

READ_AFTER_WRITE_SECONDS = getattr(settings, "READ_AFTER_WRITE_SECONDS", 5)
REPLICA_DEAD_TIMEOUT = getattr(settings, "REPLICA_DEAD_TIMEOUT", 60)

# Replication lag in seconds on a PostgreSQL standby. pg_last_xact_replay_timestamp() is the time
# of the last transaction replayed, so on an idle primary it keeps growing even though the standby
# has caught up; when everything received has been replayed the lag is therefore reported as zero.
# On a primary both LSN functions and the timestamp are NULL, so the result is NULL.
REPLICA_LAG_SQL = (
    "SELECT CASE WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() THEN 0 "
    "ELSE EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) END::FLOAT"
)

# Models used by the expensive analytics/reporting endpoints.  Django's
# database-router API receives the model (and query hints), not the request,
# so routing by model is the reliable way to keep analytics reads on the
# dedicated read replica without coupling the router to URL/middleware state.
ANALYTICS_READ_REPLICA_MODELS = {
    ("auth", "user"),
    ("dashboard", "issue"),
    ("dashboard", "pullrequest"),
    ("progress", "lessonprogress"),
    ("challenges", "challengecompletion"),
    ("progress", "codesubmission"),
    ("progress", "dailyactivity"),
    ("progress", "quizattempt"),
    ("progress", "userbadge"),
    ("progress", "streakprofile"),
    ("progress", "weeklygoal"),
    ("progress", "season"),
    ("progress", "trackmilestone"),
    ("progress", "usermilestonecompletion"),
    ("progress", "exerciseattempt"),
    ("progress", "xpevent"),
    ("progress", "badge"),
    ("content", "lesson"),
    ("audit", "auditevent"),
}


def mark_user_dirty(user_id: int) -> None:
    """
    Mark a user as having just performed a write.
    Their reads will be routed to the primary for READ_AFTER_WRITE_SECONDS.
    """
    if user_id:
        cache_key = f"raw_dirty:{user_id}"
        cache.set(cache_key, 1, timeout=READ_AFTER_WRITE_SECONDS)


def is_user_dirty(user_id: Optional[int]) -> bool:
    """
    Return True if the user recently performed a write and should read from primary.
    """
    if not user_id:
        return False
    return bool(cache.get(f"raw_dirty:{user_id}"))


class use_primary(ContextDecorator):
    """
    Keep every read on the primary inside the block (or the decorated function).

    The router cannot see a request, a Celery task or a webhook handler, only the query, so code
    that writes and then has to read its own write outside a transaction, or that must never see
    replica data, says so explicitly::

        with use_primary():
            order = Order.objects.get(pk=order_id)

        @use_primary()
        def handle_payment_webhook(event): ...

    Blocks can be nested. Writes always go to the primary anyway.
    """

    def __enter__(self):
        _local.primary_pins = getattr(_local, "primary_pins", 0) + 1
        return self

    def __exit__(self, *exc_info):
        _local.primary_pins = max(0, getattr(_local, "primary_pins", 1) - 1)
        return False


def is_primary_pinned() -> bool:
    """True while inside :class:`use_primary`."""
    return getattr(_local, "primary_pins", 0) > 0


class PrimaryReplicaRouter:
    """
    A database router to route read operations to read replicas using
    weighted round-robin, with read-after-write consistency and automatic
    replica health monitoring.

    Configure replicas via settings.DATABASE_REPLICAS:
        DATABASE_REPLICAS = [
            {"NAME": "replica1", "WEIGHT": 2},
            {"NAME": "replica2", "WEIGHT": 1},
        ]

    Each name must match a key in settings.DATABASES.
    """

    def __init__(self):
        # Support both old single "replica" key and new DATABASE_REPLICAS list
        replica_configs = getattr(settings, "DATABASE_REPLICAS", None)
        if replica_configs:
            self.replicas = [
                r["NAME"] for r in replica_configs if r["NAME"] in settings.DATABASES
            ]
            self._weights = {r["NAME"]: r.get("WEIGHT", 1) for r in replica_configs}
        else:
            # Backwards-compat: pick up all DB keys starting with "replica"
            self.replicas = [
                db for db in settings.DATABASES if db.startswith("replica")
            ]
            self._weights = {r: 1 for r in self.replicas}

        self._dead_replicas: dict[str, float] = {}
        self._dead_timeout = REPLICA_DEAD_TIMEOUT
        self._lock = threading.Lock()
        # alias -> (lag seconds, time measured); keeps lag checks off the hot path
        self._lag_cache: dict[str, tuple[float, float]] = {}
        # Why the last _probe_and_select / _select_specific_replica call fell back (per thread)
        self._tls = threading.local()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _mark_dead(self, replica: str) -> None:
        with self._lock:
            self._dead_replicas[replica] = time.time()
        logger.warning(
            "Replica %s marked as dead; will retry after %ss",
            replica,
            self._dead_timeout,
        )

    def _revive_if_timeout(self, replica: str, now: float) -> bool:
        """Return True if dead replica timeout has passed and it should be retried."""
        with self._lock:
            dead_since = self._dead_replicas.get(replica)
            if dead_since is None:
                return True
            if now - dead_since > self._dead_timeout:
                del self._dead_replicas[replica]
                return True
        return False

    def _get_healthy_replicas(self) -> list[str]:
        now = time.time()
        return [r for r in self.replicas if self._revive_if_timeout(r, now)]

    def _weighted_choice(self, available: list[str]) -> Optional[str]:
        """Pick one replica using weighted random selection."""
        if not available:
            return None
        total = sum(self._weights.get(r, 1) for r in available)
        threshold = random.uniform(0, total)
        cumulative = 0
        for r in available:
            cumulative += self._weights.get(r, 1)
            if cumulative >= threshold:
                return r
        return available[-1]

    def _lag_limit(self) -> float:
        """Most seconds a replica may be behind and still serve reads. 0 turns the check off.

        Defaults to READ_AFTER_WRITE_SECONDS: past that window a user's own write is no longer
        pinned to the primary, so a replica further behind than that could show them stale data.
        """
        limit = getattr(settings, "REPLICA_MAX_LAG_SECONDS", None)
        if limit is None:
            limit = getattr(
                settings, "READ_AFTER_WRITE_SECONDS", READ_AFTER_WRITE_SECONDS
            )
        return float(limit)

    def _replica_lag(self, alias: str) -> Optional[float]:
        """
        Seconds the replica is behind, ``inf`` when it could not be measured, or ``None`` when lag
        is not checked (disabled, or a backend that has no replication to measure).
        """
        if self._lag_limit() <= 0:
            return None
        conn = connections[alias]
        if getattr(conn, "vendor", None) != "postgresql":
            return None

        ttl = float(getattr(settings, "REPLICA_LAG_CACHE_SECONDS", 2))
        now = time.monotonic()
        cached = self._lag_cache.get(alias)
        if cached and now - cached[1] < ttl:
            return cached[0]

        try:
            with conn.cursor() as cursor:
                cursor.execute(REPLICA_LAG_SQL)
                row = cursor.fetchone()
            lag = float(row[0]) if row and row[0] is not None else 0.0
        except Exception as exc:
            # A replica whose lag cannot be read is not trusted with reads.
            logger.warning("Could not measure replication lag of %s: %s", alias, exc)
            lag = float("inf")

        self._lag_cache[alias] = (lag, now)
        metrics.record_lag(alias, lag)
        return lag

    def _is_too_far_behind(self, alias: str) -> bool:
        lag = self._replica_lag(alias)
        if lag is None:
            return False
        too_far = lag > self._lag_limit()
        if too_far:
            logger.warning(
                "Replica %s is %.1fs behind (limit %.1fs); reads stay on the primary.",
                alias,
                lag,
                self._lag_limit(),
            )
        return too_far

    def _pick_specific(self, alias: str) -> tuple[str, str]:
        """A dedicated replica if it is reachable and close enough, else the primary and why."""
        if not self._revive_if_timeout(alias, time.time()):
            return "default", metrics.REASON_UNAVAILABLE
        conn = connections[alias]
        try:
            if conn.connection is None:
                conn.ensure_connection()
        except OperationalError as exc:
            logger.warning("Replica %s health check failed: %s", alias, exc)
            self._mark_dead(alias)
            return "default", metrics.REASON_UNAVAILABLE
        if self._is_too_far_behind(alias):
            return "default", metrics.REASON_LAGGING
        return alias, metrics.REASON_REPLICA

    def _pick_from_pool(self) -> tuple[str, str]:
        """
        From the healthy replicas, try to establish a connection and check lag.
        Returns the alias to use and the reason (falls back to 'default').
        """
        available = self._get_healthy_replicas()
        random.shuffle(available)  # distribute probes randomly

        tried: set[str] = set()
        lagging = 0
        for _ in range(len(available)):
            replica = self._weighted_choice([r for r in available if r not in tried])
            if replica is None:
                break
            tried.add(replica)
            conn = connections[replica]
            try:
                if conn.connection is None:
                    conn.ensure_connection()
            except OperationalError as exc:
                logger.warning("Replica %s health check failed: %s", replica, exc)
                self._mark_dead(replica)
                continue
            if self._is_too_far_behind(replica):
                lagging += 1
                continue
            return replica, metrics.REASON_REPLICA

        if tried:
            logger.warning(
                "All read replicas are unavailable or lagging. Falling back to primary."
            )
        return "default", (
            metrics.REASON_LAGGING if lagging else metrics.REASON_UNAVAILABLE
        )

    # These two return just an alias and are the points to override when changing the strategy
    # (see docs/DATABASE_ROUTING.md); the reason for a fallback is kept on the side for the metrics.
    def _select_specific_replica(self, alias: str) -> str:
        chosen, self._tls.reason = self._pick_specific(alias)
        return chosen

    def _probe_and_select(self) -> str:
        chosen, self._tls.reason = self._pick_from_pool()
        return chosen

    def _route_choice(self, chosen: str) -> str:
        """Count a choice made by one of the two methods above."""
        if chosen == "default":
            reason = getattr(self._tls, "reason", metrics.REASON_UNAVAILABLE)
        else:
            reason = metrics.REASON_REPLICA
        return self._route(chosen, reason)

    @staticmethod
    def _route(alias: str, reason: str) -> str:
        metrics.record_route(alias, reason)
        return alias

    # ── Router API ────────────────────────────────────────────────────────────

    def db_for_read(self, model, **hints):
        """
        Route reads to a healthy replica unless:
        - We are running tests (always use default for determinism).
        - The code asked for the primary with use_primary().
        - We are inside an atomic write block on the primary (transactional consistency).
        - The current user recently performed a write (read-after-write consistency).
        - No replica is reachable, or every reachable one is further behind than the lag limit.
        Every decision is counted in db_read_routing_total by target and reason.
        """
        if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
            return "default"

        if is_primary_pinned():
            return self._route("default", metrics.REASON_PINNED)

        # Respect Django's atomic blocks on primary
        if transaction.get_connection("default").in_atomic_block:
            return self._route("default", metrics.REASON_ATOMIC)

        # Read-after-write: check thread-local first (set by middleware), then cache
        user_id = getattr(_local, "user_id", None)
        if is_user_dirty(user_id):
            logger.debug("Read-after-write: routing user %s read to primary.", user_id)
            return self._route("default", metrics.REASON_READ_AFTER_WRITE)

        # Analytics/reporting reads get their own replica when it is explicitly
        # configured. If the dedicated replica is not configured, preserve the
        # existing generic replica behaviour (or fall back to primary).
        meta = getattr(model, "_meta", None)
        model_key = (
            getattr(meta, "app_label", None),
            getattr(meta, "model_name", None),
        )
        if model_key in ANALYTICS_READ_REPLICA_MODELS:
            if "read_replica" not in settings.DATABASES:
                return self._route("default", metrics.REASON_NO_REPLICA)
            return self._route_choice(self._select_specific_replica("read_replica"))

        if not self.replicas:
            return self._route("default", metrics.REASON_NO_REPLICA)

        return self._route_choice(self._probe_and_select())

    def db_for_write(self, model, **hints):
        """All writes go to primary."""
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {"default", "read_replica"} | set(self.replicas)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Migrations must only run on the primary database."""
        if db == "read_replica" or db in self.replicas or db.startswith("replica"):
            return False
        return True

    # ── Public helpers for health views ──────────────────────────────────────

    def get_replica_lag_info(self) -> list[dict]:
        """
        Query replication lag from each configured replica.
        Returns a list of dicts with alias, lag_seconds, and status.
        """
        results = []
        for alias in self.replicas:
            info: dict = {"alias": alias, "lag_seconds": None, "status": "unknown"}
            try:
                conn = connections[alias]
                with conn.cursor() as cursor:
                    cursor.execute(REPLICA_LAG_SQL)
                    row = cursor.fetchone()
                    lag = round(row[0], 3) if row and row[0] is not None else 0.0
                    info["lag_seconds"] = lag
                    threshold = getattr(settings, "REPLICA_LAG_ALERT_SECONDS", 30)
                    info["status"] = "lagging" if lag > threshold else "healthy"
            except Exception as exc:
                info["status"] = "error"
                info["error"] = str(exc)
            results.append(info)
        return results
