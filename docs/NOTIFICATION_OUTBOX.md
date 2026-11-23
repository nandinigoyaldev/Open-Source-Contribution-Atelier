# Notification Outbox

How a notification is recorded in the same database transaction as the change it is about, and handed to the [delivery ledger](NOTIFICATION_DELIVERY_LEDGER.md) afterwards. Code: `backend/apps/notifications/outbox.py`, `models.py` (`NotificationOutbox`), `tasks.py`, `metrics.py`.

## The problem

Notifying straight from the code that changes data can go wrong two ways:

* the notification goes out, then the transaction rolls back: a notification about something that never happened,
* the transaction commits, then the process dies before anything was queued: a change nobody hears about.

## How it works

```
 your transaction                      dispatcher (worker)                  delivery ledger
 ----------------                      -------------------                  ---------------
 change data
 enqueue_notification()  --commit-->   claim row (SKIP LOCKED + lease)
   writes NotificationOutbox           dispatch_notification(dedupe_key=idempotency_key)
                                         writes Notification + NotificationDelivery rows
                                       mark row dispatched (same transaction)
                                       then start the deliveries           -> channels, retries, dead letters
```

1. `enqueue_notification(...)` inserts a `NotificationOutbox` row. Called inside the `transaction.atomic()` block of the change, the row commits or rolls back with it. After the commit it queues `dispatch_outbox_row` as a fast path (`transaction.on_commit`; nothing is queued for a rolled back transaction).
2. If that task is never queued or never runs (broker down, process killed), the periodic `dispatch_notification_outbox` task (every 30 s, Celery beat) finds the row anyway. A committed change cannot lose its notification.
3. The dispatcher claims due rows, calls `dispatch_notification` (which writes the `Notification` and one `NotificationDelivery` per enabled channel) and marks the row `dispatched` **in one transaction**, then starts the deliveries. Channels are never called while that transaction is open. From there the ledger owns everything: per-channel attempts, retries, backoff, dead letters.

```python
from django.db import transaction
from apps.notifications.delivery import make_dedupe_key
from apps.notifications.outbox import enqueue_notification

with transaction.atomic():
    user_badge = UserBadge.objects.create(user=user, badge=badge)
    enqueue_notification(
        user, "badge", "New badge", f"You earned {badge.name}",
        idempotency_key=make_dedupe_key("badge", user.id, badge.id),
        source=f"progress.UserBadge:{user_badge.pk}",
    )
```

## Idempotency

`(recipient, idempotency_key)` is unique. Enqueueing the same key again returns the existing row and queues nothing. Without a key every call is a new notification. The key is also used as the `dedupe_key` of the ledger deliveries, so a worker that dies after writing the deliveries but before marking the row cannot cause a second notification: the retry finds the deliveries and reuses them.

## Row states

| Status | Meaning |
|---|---|
| `pending` | waiting for `next_attempt_at` |
| `processing` | claimed by a worker (`locked_by`, `locked_at`) |
| `dispatched` | handed to the ledger; the ledger tracks delivery from here |
| `dead` | gave up; a `NotificationDeadLetter` with channel `outbox` holds the intent |

### Claiming

A claim is a short transaction: `SELECT ... FOR UPDATE SKIP LOCKED` on due rows (`pending` with `next_attempt_at` in the past, or `processing` with an expired lease), then one `UPDATE` to `processing`. Concurrent workers get different rows and never wait for each other. The `UPDATE` repeats the due condition, so claims stay exclusive even on a database without row locks (SQLite in tests). Every claim counts as an attempt.

If a worker is too slow and its lease (`NOTIFICATION_OUTBOX_LEASE_SECONDS`) expires, another worker takes the row. The slow worker's final write is conditional on its own claim token, so it changes nothing and its notification rows are rolled back.

### Retries and dead letters

A failed hand-off (database error, anything raised while writing the deliveries) goes back to `pending` with `next_attempt_at` pushed out by 30 s, 60 s, 120 s ... (capped at 1 h). The row becomes `dead` after `NOTIFICATION_OUTBOX_MAX_ATTEMPTS` claims, immediately for a permanent error (`ValueError`, `TypeError`...; same classification as the ledger, `delivery.classify_failure`), and when workers keep dying on it (more claims than attempts allowed). Dead rows are never picked up again until someone requeues them.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `NOTIFICATION_OUTBOX_MAX_ATTEMPTS` | 5 | claims a row gets before it is dead |
| `NOTIFICATION_OUTBOX_LEASE_SECONDS` | 120 | how long a worker may hold a row |
| `NOTIFICATION_OUTBOX_BACKOFF_SECONDS` | 30 | first retry delay, doubles each time |
| `NOTIFICATION_OUTBOX_BATCH_SIZE` | 100 | rows per claim |

Dispatched rows are removed by `purge_notification_ledger_task` after `NOTIFICATION_DELIVERY_RETENTION_DAYS` (0 keeps them). Dead rows are kept.

## Running the dispatcher

* Celery beat: `dispatch-notification-outbox` is scheduled in `CELERY_BEAT_SCHEDULE` (every 30 s).
* By hand or without beat: `python manage.py dispatch_notification_outbox [--batch-size N] [--max-rows N] [--watch --interval S]`.

## Metrics

A Prometheus collector (`metrics.OutboxCollector`, registered when the notifications app loads) reads the table at scrape time, so there is no job to keep alive:

| Metric | Meaning |
|---|---|
| `notifications_outbox_rows{status}` | rows per status (`pending`, `processing`, `dispatched`, `dead`) |
| `notifications_outbox_overdue_rows` | rows due now; should stay near zero |
| `notifications_outbox_oldest_backlog_age_seconds` | age of the oldest row not yet dispatched (0 when none) |
| `notifications_outbox_oldest_dead_age_seconds` | time since the oldest dead row failed (0 when none) |

Suggested alerts: `notifications_outbox_oldest_backlog_age_seconds > 300` (dispatcher not keeping up or not running), `notifications_outbox_rows{status="dead"} > 0`.

## Reconciliation

```
python manage.py reconcile_notification_outbox [--json] [--since-days 7] [--dead-limit 20]
                                               [--fail-on-dead] [--max-age SECONDS]
                                               [--requeue-dead [--id N ...]]
```

Prints rows per status, backlog, overdue rows, rows whose lease expired (`stale_processing`), the oldest backlog and dead ages, the dead rows with their last error, and `dispatched_with_failed_deliveries`: rows that were handed over fine but whose ledger deliveries ended `failed`. `--fail-on-dead` and `--max-age` make it exit with an error, so it works from cron or a health check. `--requeue-dead` gives dead rows a fresh set of attempts once the cause is fixed.

## Tests and limits

`backend/apps/notifications/tests/test_notification_outbox.py` covers rollback and commit of the enqueue (including `on_commit` behaviour and a dead broker), idempotency, hand-off into the ledger, claims and lease takeover, retries, backoff, dead letters, metrics, reconciliation and the commands.

Not covered by automated tests: PostgreSQL row locking under real concurrency (the tests run on SQLite, which ignores `FOR UPDATE`; they check that the claim asks for `skip_locked=True` and that the conditional `UPDATE` keeps it exclusive), and a real broker and worker.

Existing code that notifies directly (the badge and peer review signal handlers) is unchanged; move a caller over by replacing its direct notification with `enqueue_notification` inside its transaction.
