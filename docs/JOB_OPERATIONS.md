# Background Job Operations

Admin page: `/admin/celery`. API: `/api/admin/` (also `/api/monitoring/`). Everything on this page and API is staff only (`IsAdminUser`). That includes the task run list, the task statistics and the test trigger, which used to be open to any logged in user.

## What is tracked

Each Celery task has one `TaskRun` row, keyed by its task id.

| Status | Meaning |
|---|---|
| `PENDING` | Published to the broker, not picked up yet. `queued_at` is the publish time. |
| `STARTED` | A worker is running it. Holds a lease. |
| `SUCCESS`, `FAILURE` | Finished. |
| `RETRY` | Waiting to run again: Celery's own retry, or an operator retry. |
| `STUCK` | Was `STARTED` and its lease expired with no result. The worker probably died. |
| `CANCELLED` | Cancelled by an operator. |

`PENDING` rows come from the `before_task_publish` signal. A task that is run eagerly (tests, `CELERY_TASK_ALWAYS_EAGER`) is never published and has no `PENDING` row.

## Leases and the reaper

When a worker starts a task it takes a lease: `heartbeat_at` is now and `lease_expires_at` is now plus the task's `time_limit` and 60 seconds, or `TASK_RUN_LEASE_SECONDS` (900) for a task with no time limit. Finishing, failing or retrying releases it.

A long task can push its lease forward and prove it is alive:

```python
from apps.monitoring.job_ops import touch_heartbeat

touch_heartbeat(self.request.id)  # inside the task, for example once per batch
```

`monitoring.reap_stuck_task_runs` (Celery beat, every minute) marks every `STARTED` run whose lease expired as `STUCK` and writes a `task_run.marked_stuck` audit event for each. It is idempotent: a second pass finds nothing. `python manage.py reap_stuck_task_runs` does the same by hand or from cron. If a task marked `STUCK` later finishes or sends a heartbeat, the result replaces `STUCK`.

A run with no lease (rows from before this feature) is never marked stuck.

`monitoring.requeue_orphaned_runs` (beat, every minute) sends a `STUCK` run again for tasks that opted in with `failover_requeue=True`. See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).

## Operator actions

Both are `POST`, staff only, answer with a `status` field, and write an audit event ([AUDIT_EVENTS.md](AUDIT_EVENTS.md)) only when they change something.

| Action | Allowed from | Result |
|---|---|---|
| `celery-task-runs/<id>/retry/` | `FAILURE`, `STUCK`, `CANCELLED` | `202 queued`: the run moves to `RETRY`, `retry_count` goes up, a new task is sent (its id is `new_task_id`). From `PENDING`, `STARTED`, `RETRY`: `200 already_queued`, nothing is sent. From `SUCCESS`: `409 not_retryable`. |
| `celery-task-runs/<id>/cancel/` | `PENDING`, `RETRY`, `STUCK` | `200 cancelled`: the task id is revoked (and terminated when it was `STUCK`). Already cancelled: `200 already_cancelled`. `STARTED`, `SUCCESS`, `FAILURE`: `409 not_cancellable`. |

If the broker cannot be reached, both answer `503` and leave the run as it was.

A retry sends the task name only. Arguments are not stored, only a redacted summary, so the retried task runs without arguments. Re-run tasks that need arguments from where they were first created.

## What the dashboard shows

`GET /api/admin/celery-stats/` adds to the existing counts:

* `pending_runs` and `oldest_queued_age_seconds`: how many runs wait for a worker and how long the oldest has waited;
* `stuck_runs`: runs currently `STUCK`;
* `worker_heartbeat`: `status` is `down` when no worker answers a ping, `degraded` when workers answer but a run is `STUCK`, otherwise `healthy`. `workers_alive` lists who answered and `last_task_heartbeat_at` is the newest heartbeat from a running task.

Each run in `celery-task-runs/` has `queued_at`, `heartbeat_at`, `lease_expires_at`, `queue_age_seconds` (pending runs only) and the failure reason in `error_message`.

## Redaction

Task arguments are redacted when the run is recorded (`apps/monitoring/utils/redaction.py`: values under keys like `password`, `token`, `secret`). `args_summary` and `error_message` are redacted again with `apps/audit/redaction.py` when they are returned or broadcast, so a secret in an old row or in an exception message is not shown.

## Settings

| Setting | Default | |
|---|---|---|
| `TASK_RUN_LEASE_SECONDS` | `900` | lease for a task without a `time_limit` |

The Celery app is not configured in `backend/config` in this repository, so the beat schedule entry only runs where a Celery beat process loads these settings. Where there is none, run `reap_stuck_task_runs` from cron.
