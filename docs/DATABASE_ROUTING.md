# Database Routing Architecture

This document describes the database routing architecture for the Open-Source Contribution Atelier platform. The implementation lives in `backend/config/db_router.py`, `backend/config/raw_middleware.py` and `backend/config/db_router_metrics.py`.

## Read/Write Routing Rules
The application relies on Django's ORM database routing feature to separate read and write database operations.
- **Writes:** All `INSERT`, `UPDATE`, and `DELETE` operations are strictly routed to the primary database (`default`).
- **Reads:** `SELECT` operations go to a healthy, close-enough read replica, unless one of the rules below keeps them on the primary.

A read stays on the primary, in this order of precedence:

| Reason (metric label) | When |
|---|---|
| `pinned_primary` | The code is inside `use_primary()` (see below). |
| `atomic_block` | A `transaction.atomic()` block is open on the primary, so the read sees the transaction's own writes. |
| `read_after_write` | The current user wrote less than `READ_AFTER_WRITE_SECONDS` ago. |
| `no_replica` | No replica is configured. |
| `replica_unavailable` | Every replica is unreachable (or marked dead, see Fallback). |
| `replica_lagging` | Every reachable replica is further behind than the lag limit. |

Reads that do go to a replica are counted as `replica`.

## Read-after-write consistency
After a mutating request (`POST`, `PUT`, `PATCH`, `DELETE`) by a user, `ReadAfterWriteMiddleware` flags that user for `READ_AFTER_WRITE_SECONDS` (default 5). While flagged, all of the user's reads use the primary, so they never fail to see what they just saved.

The user is taken from the Django session, or, for API clients, from the `Authorization: Bearer` JWT. DRF only checks the token inside the view, so the middleware reads the user id from the token itself (signature and expiry are verified, no database lookup). The id is used only to choose a database, never for authorization. Anonymous requests are not tracked.

## Transaction Handling Behavior
To ensure transactional consistency and prevent "stale reads" immediately after writes:
- If a query is executed inside an active write transaction block (`transaction.atomic()` or similar), the router detects it and routes the reads to `default`.

## Choosing the primary explicitly: `use_primary()`
The router sees queries, not requests, so code that is not a web request (Celery tasks, webhook handlers, management commands) gets no read-after-write protection from the middleware. When such code writes and then reads its own data outside a transaction, or must never see replica data, pin it:

```python
from config.db_router import use_primary

with use_primary():
    order = Order.objects.get(pk=order_id)

@use_primary()
def handle_payment_webhook(event): ...
```

Blocks can be nested, the pin is per thread, and it is released when the block raises.

## Replica Configuration Steps
Replicas are configured in `backend/config/settings.py`.

- `DATABASE_REPLICAS` lists the replicas the router may use, each with an optional weight; every `NAME` must be a key in `DATABASES`:
  ```python
  DATABASES = {
      "default": dj_database_url.config(env="DATABASE_URL"),
      "replica_1": dj_database_url.config(env="REPLICA_1_DATABASE_URL"),
      "replica_2": dj_database_url.config(env="REPLICA_2_DATABASE_URL"),
  }
  DATABASE_REPLICAS = [
      {"NAME": "replica_1", "WEIGHT": 2},
      {"NAME": "replica_2", "WEIGHT": 1},
  ]
  ```
  Without `DATABASE_REPLICAS`, every `DATABASES` key that starts with `replica` is used with weight 1.
- Setting `DB_REPLICA_HOST` adds a dedicated `read_replica` used for the analytics and reporting models. If it is not set, those reads follow the normal rules above.
- Migrations only ever run on the primary.

| Setting | Default | Meaning |
|---|---|---|
| `READ_AFTER_WRITE_SECONDS` | 5 | How long a user's reads stay on the primary after a write. |
| `REPLICA_MAX_LAG_SECONDS` | `READ_AFTER_WRITE_SECONDS` | Most seconds a replica may be behind and still serve reads. `0` turns the check off. |
| `REPLICA_LAG_CACHE_SECONDS` | 2 | How long a lag measurement is reused, so the check is not a query per read. |
| `REPLICA_DEAD_TIMEOUT` | 60 | Seconds before a replica that failed to connect is tried again. |
| `REPLICA_LAG_ALERT_SECONDS` | 30 | Lag above which `/health/db/replication-lag/` answers 503. |

## Replica lag
A replica that has fallen behind must not serve reads: once a user's read-after-write window has passed, a stale replica could show them old data. The default limit equals the window (`READ_AFTER_WRITE_SECONDS`).

- Lag is measured on PostgreSQL replicas only (other backends have nothing to measure and are not checked) and cached for `REPLICA_LAG_CACHE_SECONDS`.
- A replica above the limit is skipped for reads but is **not** marked dead; it is used again as soon as a new measurement is back under the limit.
- A replica whose lag cannot be read is treated as lagging, not trusted.
- The lag query reports `0` when the replica has replayed everything it received. The older query (`now() - pg_last_xact_replay_timestamp()`) keeps growing while the primary is idle, which made a healthy replica look lagging.
- `GET /health/db/replication-lag/` reports the lag per replica and answers 503 above `REPLICA_LAG_ALERT_SECONDS`; `python manage.py check_replication_lag` does the same from the command line.

## Graceful Fallback Scenarios
The `PrimaryReplicaRouter` incorporates built-in health checking and fallback logic.
- If a read replica becomes unresponsive or throws an `OperationalError`, the router marks it dead and uses another replica.
- A dead dedicated analytics replica is also not retried on every read; it waits for `REPLICA_DEAD_TIMEOUT`.
- If all read replicas are unavailable or lagging, read traffic falls back to the primary (`default`) and a warning is logged.
- Dead replicas are retried after `REPLICA_DEAD_TIMEOUT` (default 60 seconds).

## Observability
Every routed read is counted, with the database it went to and why:

- `db_read_routing_total{target="primary|replica", reason="..."}` (Prometheus counter, reasons as in the table above)
- `db_replica_lag_seconds{replica="..."}` (Prometheus gauge, the latest measurement)

Useful questions: what share of reads reaches the replicas (`target="replica"`), whether `replica_lagging` or `replica_unavailable` is rising, and whether `read_after_write` is so high that replicas are barely used. The counters are per process. During test runs the router always answers `default` and is not counted.

## Guidelines for Extending
The router picks among healthy replicas with weighted random selection and tracks health with a time-based dead list. To change the strategy without a larger redesign:
- **Advanced Load Balancing:** override `_probe_and_select()` (pool) or `_select_specific_replica()` (the dedicated replica); both return a database alias. Latency-based routing or an external service mesh can plug in there.
- **External Health Checks:** instead of testing availability on the first failure inside the router, integrate a heartbeat check through Redis or Memcached to share replica health across instances instantly.
- **Lag source:** `REPLICA_LAG_SQL` in `db_router.py` is the one query used by both routing and the health view.

## Tests
`backend/tests/test_db_router_lag.py` covers lag-aware routing (within, at and over the limit, unreadable lag, caching, switching off, non-PostgreSQL), `use_primary()`, the routing reasons and metrics, and read-after-write for JWT clients, including a request through the real middleware stack.

Not covered by automated tests: a real PostgreSQL replica. The lag query is checked against a mock, so run `python manage.py check_replication_lag` against a staging replica before relying on it.
