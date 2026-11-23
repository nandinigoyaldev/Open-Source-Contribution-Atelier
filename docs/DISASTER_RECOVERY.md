# Disaster Recovery: Realtime and Worker Failover

What happens to websockets and background jobs when Redis, a realtime instance or a worker goes away, what the app does on its own, and what an operator does.

## Recovery objectives

| What fails | What the app does | Objective |
|---|---|---|
| Redis dies under the channel layer | `ResilientChannelLayer` switches that process to an in-memory layer on the first failed call. Websockets stay up, fan-out is limited to the process. | 0 s to switch (no client sees an error) |
| Redis comes back | The degraded process probes Redis at most every 15 s and fails back on its own once no connection is subscribed on the fallback. If connections are still subscribed it stays degraded and `/health/failover/` says to recycle it. | 15 s probe interval, then the next client reconnect |
| A realtime instance dies | The load balancer takes it out (`/health/live/`), the client reconnects with backoff (`frontend/src/lib/ws.ts`) and resumes from its cursor. Chat sends `since_id` and gets only the missed messages in a `history_sync` frame. | Client backoff, no message lost or repeated |
| A worker dies mid task | Its lease expires, the reaper marks the run `STUCK`, and the requeue step sends it again if the task opted in. | At most lease time + 60 s |
| The database is down | `/health/failover/` answers 503 and the instance leaves rotation. | n/a, restore from backup |

Message data is never held only in the channel layer: chat messages are written to the database before they are fanned out, which is why a reconnect with a cursor loses nothing. The channel layer itself is not replicated and anything in flight on a dead Redis is gone (RPO of a few seconds of presence and typing events, zero for stored messages and job rows).

## Health states

`GET /health/failover/` reports each dependency as one of:

* `ready`: working.
* `degraded`: serving on a fallback or with a backlog.
* `unavailable`: not working.

| Dependency | degraded when | unavailable when |
|---|---|---|
| `database` | never | `SELECT 1` fails |
| `cache` | never | the cache round trip fails |
| `realtime` | the channel layer is on the in-memory fallback (after a Redis failure, or Redis was unreachable at startup) | no channel layer |
| `workers` | a run is `STUCK` or past its lease, or the oldest queued run has waited 5 minutes | the oldest queued run has waited 30 minutes |

The overall `status` is `unavailable` (HTTP 503) only when a critical dependency is unavailable. By default that is the database only (`FAILOVER_CRITICAL_DEPENDENCIES`). Everything else down is `degraded` and answers 200, so one broken optional dependency does not pull every instance out of rotation. Add `cache` to the critical list if you want Redis loss to fail the instance.

The response carries states and counts only: no hostnames, credentials or exception text. Point load balancer health checks at `/health/live/` for liveness and use `/health/failover/` for alerts and dashboards. `/health/` and `/health/ready/` are unchanged.

Thresholds: `FAILOVER_QUEUE_AGE_DEGRADED_SECONDS` (300) and `FAILOVER_QUEUE_AGE_UNAVAILABLE_SECONDS` (1800).

## Worker failover

Leases and the reaper are described in [JOB_OPERATIONS.md](JOB_OPERATIONS.md). On top of them, `monitoring.requeue_orphaned_runs` (Celery beat, every minute) sends a `STUCK` run again, but only when it is safe:

* The task opted in with `@shared_task(failover_requeue=True)`, or its name is in `FAILOVER_REQUEUE_TASKS`. A worker that was only slow may still finish the first copy, so the task has to be idempotent.
* The run has no arguments. Arguments are not stored (only a redacted summary), so they cannot be replayed. Runs with arguments stay `STUCK` for an operator.
* Fewer than `FAILOVER_REQUEUE_MAX_ATTEMPTS` (3) requeues of that task in the last `FAILOVER_REQUEUE_WINDOW_SECONDS` (1 h). A task that kills its worker every time is left `STUCK` instead of looping.

Each run is sent at most once: the requeue claims the row with a conditional update, so two beat processes, or the same pass run twice, dispatch once. If the broker is down the run stays `STUCK` and the next pass tries again.

## Runbook

### Redis outage

1. `GET /health/failover/` shows `realtime: degraded` (and `cache: unavailable` if the cache is on that Redis).
2. Restore Redis. Do not flush it.
3. Within about 15 s a process with no connected clients fails back by itself. For a process that still shows `primary_recovered: true`, do a rolling restart of the realtime workers, one at a time. Clients reconnect and resume from their cursor.
4. Confirm `realtime: ready` on every instance.

### Realtime instance lost

1. The load balancer drops it after `/health/live/` fails.
2. Clients reconnect on their own. Check that chat clients send `since_id` (the last message id they saw) and handle `history_sync`. If `resync_required` is true the cursor is older than retention and the client must reload the room.
3. Replace the instance.

### Worker lost

1. Wait one lease (task `time_limit` + 60 s, or `TASK_RUN_LEASE_SECONDS`), or run `python manage.py reap_stuck_task_runs`.
2. Opted-in no-argument tasks are requeued by the next beat pass. Look at what is left: `GET /api/admin/celery-task-runs/?status=STUCK`.
3. Retry or cancel the rest from the admin page, re-running tasks that need arguments from where they were created. Do not delete queue keys or task rows.

## Failure drill

The drill is automated and repeatable, needs no Redis, broker or worker, and checks the objectives above. The dead Redis is a channel layer pointed at a closed local port, so the failures are real connection errors.

```bash
cd backend
REDIS_URL=redis://127.0.0.1:1/0 pytest apps/health/test_failover.py --no-migrations
```

It covers: Redis dying under a live channel layer, failback refused while connections are on the fallback and accepted once they are gone, probe rate limiting, a chat client reconnecting after the outage with its cursor and getting the missed messages once each, a worker dying mid task and its run being requeued exactly once, the attempt cap, a broker outage during requeue, and every health state and HTTP code.

Not covered by the automated drill: a real multi-region switch, real Redis or Postgres failover, and load balancer behaviour. Rehearse those in a staging environment using the runbook above.
