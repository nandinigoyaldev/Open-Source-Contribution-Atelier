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
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db import connections, transaction
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)

# Thread-local storage for per-request write tracking
_local = threading.local()

READ_AFTER_WRITE_SECONDS = getattr(settings, "READ_AFTER_WRITE_SECONDS", 5)
REPLICA_DEAD_TIMEOUT = getattr(settings, "REPLICA_DEAD_TIMEOUT", 60)


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
            self.replicas = [r["NAME"] for r in replica_configs if r["NAME"] in settings.DATABASES]
            self._weights = {r["NAME"]: r.get("WEIGHT", 1) for r in replica_configs}
        else:
            # Backwards-compat: pick up all DB keys starting with "replica"
            self.replicas = [db for db in settings.DATABASES if db.startswith("replica")]
            self._weights = {r: 1 for r in self.replicas}

        self._dead_replicas: dict[str, float] = {}
        self._dead_timeout = REPLICA_DEAD_TIMEOUT
        self._lock = threading.Lock()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _mark_dead(self, replica: str) -> None:
        with self._lock:
            self._dead_replicas[replica] = time.time()
        logger.warning("Replica %s marked as dead; will retry after %ss", replica, self._dead_timeout)

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

    def _probe_and_select(self) -> str:
        """
        From healthy replicas, try to establish a connection.
        Returns the db alias to use (falls back to 'default').
        """
        available = self._get_healthy_replicas()
        random.shuffle(available)  # distribute probes randomly

        # Try replicas in weighted order
        tried = set()
        for _ in range(len(available)):
            replica = self._weighted_choice([r for r in available if r not in tried])
            if replica is None:
                break
            tried.add(replica)
            conn = connections[replica]
            try:
                if conn.connection is None:
                    conn.ensure_connection()
                return replica
            except OperationalError as exc:
                logger.warning("Replica %s health check failed: %s", replica, exc)
                self._mark_dead(replica)

        if len(tried) == len(available) and available:
            logger.warning("All read replicas are unavailable. Falling back to primary.")
        return "default"

    # ── Router API ────────────────────────────────────────────────────────────

    def db_for_read(self, model, **hints):
        """
        Route reads to a healthy replica unless:
        - We are inside an atomic write block on the primary (transactional consistency).
        - The current user recently performed a write (read-after-write consistency).
        - We are running tests (always use default for determinism).
        """
        if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
            return "default"

        # Respect Django's atomic blocks on primary
        if transaction.get_connection("default").in_atomic_block:
            return "default"

        # Read-after-write: check thread-local first (set by middleware), then cache
        user_id = getattr(_local, "user_id", None)
        if is_user_dirty(user_id):
            logger.debug("Read-after-write: routing user %s read to primary.", user_id)
            return "default"

        if not self.replicas:
            return "default"

        return self._probe_and_select()

    def db_for_write(self, model, **hints):
        """All writes go to primary."""
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {"default"} | set(self.replicas)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Migrations must only run on the primary database."""
        if db in self.replicas or db.startswith("replica"):
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
                    # PostgreSQL: pg_stat_replication or pg_last_xact_replay_timestamp
                    cursor.execute(
                        "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::FLOAT"
                    )
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
