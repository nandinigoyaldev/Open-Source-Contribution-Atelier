# Database Routing Architecture

This document describes the database routing architecture for the Open-Source Contribution Atelier platform.

## Read/Write Routing Rules
The application relies on Django's ORM database routing feature to separate read and write database operations.
- **Writes:** All `INSERT`, `UPDATE`, and `DELETE` operations are strictly routed to the primary database (`default`).
- **Reads:** All `SELECT` operations are routed to available read replica databases.

## Transaction Handling Behavior
To ensure transactional consistency and prevent "stale reads" immediately after writes:
- If a query is executed inside an active write transaction block (`transaction.atomic()` or similar), the router automatically detects the active transaction and routes subsequent read queries within that transaction to the `default` primary database.

## Replica Configuration Steps
Replicas can be easily configured using the `DATABASES` setting in `backend/config/settings.py`. 
Any database configuration whose alias begins with `replica` will be recognized and utilized by the routing mechanism.
Example Configuration:
```python
DATABASES = {
    "default": dj_database_url.config(env="DATABASE_URL"),
    "replica_1": dj_database_url.config(env="REPLICA_1_DATABASE_URL"),
    "replica_2": dj_database_url.config(env="REPLICA_2_DATABASE_URL"),
}
```

## Graceful Fallback Scenarios
The `PrimaryReplicaRouter` incorporates built-in health checking and fallback logic. 
- If a read replica becomes unresponsive or throws an `OperationalError`, the router will temporarily mark the replica as dead and fall back to other available replicas.
- If all read replicas are unavailable, read traffic safely and automatically falls back to the primary database (`default`).
- The router automatically retries "dead" replicas after a configured timeout (default 60 seconds).

## Guidelines for Extending
The current implementation utilizes randomized round-robin load balancing (`random.shuffle`) and a time-based timeout mechanism for health tracking. To extend this strategy in the future without major architectural changes:
- **Advanced Load Balancing:** Override `_get_healthy_replica()` to introduce custom weights, latency-based routing, or integrate with an external service mesh instead of random shuffle.
- **External Health Checks:** Instead of testing database availability directly on the initial failure within the router, you can integrate with an external heartbeat check via Redis or Memcached to broadcast replica health status across all Django instances instantly.
