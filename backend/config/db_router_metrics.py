"""
Routing metrics for :class:`config.db_router.PrimaryReplicaRouter`.

Every read that goes through the router is counted with the database it was sent to and the
reason, so an operator can see how much traffic the replicas really take and why reads fall
back to the primary (an open transaction, a recent write, a lagging or unreachable replica...).

Exposed as Prometheus metrics when ``prometheus_client`` is installed, and always kept in a
small in-process table as well (used by the tests and by the replication health view).
"""

import threading
from collections import Counter as _Counter

try:  # pragma: no cover - exercised implicitly depending on the environment
    from prometheus_client import Counter, Gauge

    _ROUTED = Counter(
        "db_read_routing_total",
        "Database reads by the database they were routed to and the reason.",
        ["target", "reason"],
    )
    _LAG = Gauge(
        "db_replica_lag_seconds",
        "Last measured replication lag of a read replica, in seconds.",
        ["replica"],
    )
except Exception:  # pragma: no cover
    _ROUTED = None
    _LAG = None

# Reasons a read stays on (or returns to) the primary, plus the one reason it goes to a replica.
REASON_REPLICA = "replica"
REASON_PINNED = "pinned_primary"
REASON_ATOMIC = "atomic_block"
REASON_READ_AFTER_WRITE = "read_after_write"
REASON_NO_REPLICA = "no_replica"
REASON_UNAVAILABLE = "replica_unavailable"
REASON_LAGGING = "replica_lagging"
REASON_TEST = "test_run"

_lock = threading.Lock()
_counts: "_Counter[tuple[str, str]]" = _Counter()
_lag: dict[str, float] = {}


def record_route(target: str, reason: str) -> None:
    """Count one routed read. ``target`` is the database alias that was chosen."""
    bucket = "primary" if target == "default" else "replica"
    with _lock:
        _counts[(bucket, reason)] += 1
    if _ROUTED is not None:
        _ROUTED.labels(target=bucket, reason=reason).inc()


def record_lag(replica: str, seconds: float) -> None:
    """Remember the latest lag measurement for a replica (inf means it could not be measured)."""
    with _lock:
        _lag[replica] = seconds
    if _LAG is not None and seconds != float("inf"):
        _LAG.labels(replica=replica).set(seconds)


def routing_counts() -> dict[str, int]:
    """Counts as ``{"primary:atomic_block": 3, "replica:replica": 40, ...}``."""
    with _lock:
        return {f"{bucket}:{reason}": n for (bucket, reason), n in _counts.items()}


def last_lag() -> dict[str, float]:
    with _lock:
        return dict(_lag)


def reset() -> None:
    """Forget the in-process numbers (tests)."""
    with _lock:
        _counts.clear()
        _lag.clear()
