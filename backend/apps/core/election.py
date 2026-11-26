"""
Distributed Leader Election Service for Multi-Worker Coordination.
==================================================================
Implements distributed leader election using Redis key leasing:
  SET leader_key leader_id NX EX 15

Guarantees:
  - Only the elected leader node executes scheduled fan-out broadcasting and
    notification ledger generation.
  - Heartbeat leasing: The leader must renew its lease atomically within 15s.
  - If the leader crashes or fails to renew within 15 seconds, follower nodes
    seamlessly claim leadership without missing notification windows.
  - Continuously updates Prometheus monitoring gauge:
    `notification_worker_is_leader` (1=leader, 0=follower).
"""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import cache

from apps.notifications.metrics import set_worker_is_leader_metric

logger = logging.getLogger(__name__)

DEFAULT_LEADER_KEY = "leader:notification_worker"
DEFAULT_LEASE_TTL = 15  # 15 seconds lease per requirement

# Atomic Lua Script for Lease Renewal:
# Extends expiration ONLY IF the caller still owns the leader_id lease.
_RENEW_LUA_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""

# Atomic Lua Script for Voluntary Step-down:
# Deletes the key ONLY IF the caller still owns the leader_id lease.
_STEP_DOWN_LUA_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def _get_redis_connection():
    """Obtain raw redis client from django_redis or fallback to None."""
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception as exc:
        logger.debug("Raw redis connection unavailable: %s", exc)
        return None


class LeaderElectionService:
    """
    Distributed leader election coordinator backed by Redis key leasing.
    """

    def __init__(
        self,
        key: str = DEFAULT_LEADER_KEY,
        node_id: Optional[str] = None,
        ttl: int = DEFAULT_LEASE_TTL,
        redis_client: Optional[Any] = None,
    ):
        self.key = key
        self.ttl = ttl
        self.node_id = (
            node_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        self._redis_client = redis_client
        self._is_leader: bool = False

    @property
    def redis(self):
        if self._redis_client is not None:
            return self._redis_client
        return _get_redis_connection()

    def acquire_leadership(self) -> bool:
        """
        Attempt to acquire leadership via atomic SET key node_id NX EX ttl.
        Returns True if leadership was claimed, False otherwise.
        """
        client = self.redis
        acquired = False

        if client is not None:
            try:
                # Direct Redis atomic key leasing (SET leader_id NX EX 15)
                res = client.set(self.key, self.node_id, nx=True, ex=self.ttl)
                acquired = bool(res)
            except Exception as exc:
                logger.warning("Redis error during acquire_leadership: %s", exc)
                acquired = False
        else:
            # Fallback for cache-backed local testing environments
            try:
                acquired = bool(cache.add(self.key, self.node_id, timeout=self.ttl))
            except Exception as exc:
                logger.warning("Cache fallback error during acquire: %s", exc)
                acquired = False

        self._is_leader = acquired
        set_worker_is_leader_metric(self._is_leader)

        if acquired:
            logger.info(
                "Leader election: Node '%s' claimed leadership on '%s' (TTL=%ds)",
                self.node_id,
                self.key,
                self.ttl,
            )
        else:
            logger.debug(
                "Leader election: Node '%s' failed to claim leadership on '%s'",
                self.node_id,
                self.key,
            )

        return acquired

    def renew_leadership(self) -> bool:
        """
        Atomically extend the lease if this node is still the registered leader.
        Returns True if renewed, False if the lease expired or was claimed by another node.
        """
        if not self._is_leader:
            return False

        client = self.redis
        renewed = False

        if client is not None:
            try:
                res = client.eval(
                    _RENEW_LUA_SCRIPT, 1, self.key, self.node_id, self.ttl
                )
                renewed = bool(res == 1 or res is True)
            except Exception as exc:
                logger.warning("Redis error during renew_leadership: %s", exc)
                renewed = False
        else:
            try:
                current_val = cache.get(self.key)
                if current_val == self.node_id:
                    cache.set(self.key, self.node_id, timeout=self.ttl)
                    renewed = True
            except Exception as exc:
                logger.warning("Cache fallback error during renew: %s", exc)
                renewed = False

        self._is_leader = renewed
        set_worker_is_leader_metric(self._is_leader)

        if not renewed:
            logger.warning(
                "Leader election: Node '%s' lost leadership lease on '%s'",
                self.node_id,
                self.key,
            )

        return renewed

    def step_down(self) -> bool:
        """
        Voluntarily relinquish leadership (e.g. on worker graceful shutdown).
        """
        client = self.redis
        stepped_down = False

        if client is not None:
            try:
                res = client.eval(_STEP_DOWN_LUA_SCRIPT, 1, self.key, self.node_id)
                stepped_down = bool(res == 1 or res is True)
            except Exception as exc:
                logger.warning("Redis error during step_down: %s", exc)
                stepped_down = False
        else:
            try:
                if cache.get(self.key) == self.node_id:
                    cache.delete(self.key)
                    stepped_down = True
            except Exception as exc:
                logger.warning("Cache fallback error during step_down: %s", exc)
                stepped_down = False

        self._is_leader = False
        set_worker_is_leader_metric(False)
        logger.info(
            "Leader election: Node '%s' stepped down from leadership on '%s'",
            self.node_id,
            self.key,
        )
        return stepped_down

    def is_leader(self, verify_with_storage: bool = False) -> bool:
        """
        Check whether this node currently holds the leader role.
        """
        if verify_with_storage:
            current = self.get_current_leader()
            self._is_leader = current == self.node_id
            set_worker_is_leader_metric(self._is_leader)

        return self._is_leader

    def get_current_leader(self) -> Optional[str]:
        """Inspect storage to check the active leader node ID."""
        client = self.redis
        if client is not None:
            try:
                val = client.get(self.key)
                if val:
                    return val.decode("utf-8") if isinstance(val, bytes) else str(val)
                return None
            except Exception as exc:
                logger.warning("Redis error reading current leader: %s", exc)
                return None
        try:
            val = cache.get(self.key)
            return str(val) if val else None
        except Exception:
            return None

    def run_election_cycle(self) -> bool:
        """
        Execute one heartbeat cycle:
          - If already leader, renew lease. If renewal fails, attempt re-acquire.
          - If follower, attempt to claim leadership.
        Returns True if leader, False if follower.
        """
        if self._is_leader:
            if not self.renew_leadership():
                return self.acquire_leadership()
            return True
        return self.acquire_leadership()


_default_service: Optional[LeaderElectionService] = None


def get_default_election_service() -> LeaderElectionService:
    """Return the singleton election service for the current worker process."""
    global _default_service
    if _default_service is None:
        _default_service = LeaderElectionService()
    return _default_service


def set_default_election_service(service: Optional[LeaderElectionService]) -> None:
    """Override singleton service (primarily used in tests)."""
    global _default_service
    _default_service = service


def is_worker_leader(election_service: Optional[LeaderElectionService] = None) -> bool:
    """Convenience helper to check leader status."""
    service = election_service or get_default_election_service()
    return service.is_leader()


def leader_only(task_func: Callable) -> Callable:
    """
    Decorator that ensures a scheduled task only runs on the elected cluster leader.
    Follower nodes skip execution with a logged message and return status.
    """

    @wraps(task_func)
    def wrapper(*args, **kwargs):
        # Allow disabling leader requirement in development or non-clustered test runs
        if not getattr(settings, "ENABLE_LEADER_ELECTION", True):
            return task_func(*args, **kwargs)

        election = get_default_election_service()
        if not election.is_leader():
            logger.info(
                "Skipping task '%s': Node '%s' is a follower (not elected leader)",
                task_func.__name__,
                election.node_id,
            )
            return {
                "status": "skipped",
                "reason": "not_leader",
                "task": task_func.__name__,
                "leader": election.get_current_leader(),
            }

        return task_func(*args, **kwargs)

    return wrapper


@contextmanager
def leader_guard(election_service: Optional[LeaderElectionService] = None):
    """
    Context manager for conditional leader execution blocks.
    Usage:
        with leader_guard() as is_leader:
            if is_leader:
                perform_fan_out()
    """
    service = election_service or get_default_election_service()
    yield service.is_leader()
