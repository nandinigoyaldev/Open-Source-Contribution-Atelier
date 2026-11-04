# Notification Delivery Ledger

How a notification gets from `dispatch_notification()` to a channel, how every try is written down, and what happens when something goes wrong. Code: `backend/apps/notifications/` (`tasks.py`, `delivery.py`, `retention.py`, `models.py`).

## The two tables

| Table | One row per | Says |
|---|---|---|
| `NotificationDelivery` | notification on one channel | where it stands now: `pending`, `sent`, `failed`, plus `opened` / `clicked` / `bounced` from tracking |
| `NotificationAttempt` | try at delivering it | how it got there: outcome, timing, the provider's answer |
| `NotificationDeadLetter` | delivery that was given up on | the payload and the last error, for follow-up |

`NotificationDelivery` also keeps a snapshot of the `payload`, the `dedupe_key`, the last error and its class, and the last provider answer (`provider`, `provider_message_id`, `provider_response`).

Attempt outcomes: `started` (in flight), `sent`, `transient_failure`, `permanent_failure`, `rate_limited`, `skipped` (the delivery was already sent), `abandoned` (the worker died mid-attempt).

## Deduplication

`dispatch_notification(..., dedupe_key=...)` is idempotent. Build the key from what identifies the event, not from the time:

```python
from apps.notifications.delivery import make_dedupe_key

dispatch_notification(
    user, "badge", "New badge", "You earned Streak 7",
    dedupe_key=make_dedupe_key("badge", user.id, badge.id),
)
```

Calling it again with the same key for the same recipient creates nothing and returns the first call's deliveries, so a retried signal handler or a re-run task cannot notify twice. The rule is also enforced by the database (a unique constraint on recipient, channel and key; deliveries without a key are not constrained), so two workers racing on the same event leave one notification. The notification and its deliveries are written in one transaction.

A second line of defence sits in the worker: `process_notification_delivery` is idempotent. A delivery that is already sent is never sent again (the redelivered task is recorded as `skipped`), and only one worker at a time can hold a delivery: the claim is one conditional `UPDATE`, and a claim older than `NOTIFICATION_CLAIM_LEASE_SECONDS` is treated as left by a dead worker.

## Retry classification

Each failure is classified from what the channel reports or raises:

| Class | Examples | What happens |
|---|---|---|
| `permanent` | no email address, phone number or webhook URL; HTTP 4xx other than 408, 409, 423, 425, 429; SMTP 5xx or refused recipient; bad input (`ValueError`, `TypeError`...); channel not registered | straight to the dead letters, no more tries |
| `transient` | timeouts, connection errors, HTTP 408, 429, 5xx; SMTP 4xx; any unknown error; a channel that returns plain `False` | retried with backoff (60 s, 120 s, 240 s... up to 1 h) until `NOTIFICATION_MAX_ATTEMPTS` tries are used, then dead-lettered |
| `rate_limited` | the per-user per-channel limit was hit | deferred by `NOTIFICATION_RATE_LIMIT_DELAY_SECONDS` without using up a try; dead-lettered only after `NOTIFICATION_RATE_LIMIT_MAX_DEFERRALS` deferrals |

Channels can say more than `True` or `False`. `deliver()` may return `DeliveryResult.sent(provider=..., message_id=..., status_code=..., response={...})`, `DeliveryResult.permanent_failure("...")` or `DeliveryResult.transient_failure("...")`, or raise `DeliveryError("...", status_code=503)`. A bare `True` still works. The built-in email, SMS (Twilio), webhook and Slack channels report this way.

## Recovery

A worker that is killed mid-delivery leaves a `started` attempt and a claim. `recover_stale_deliveries` runs every 5 minutes (Celery beat) and:

1. closes `started` attempts older than the claim lease as `abandoned` and counts them as a failed try,
2. queues pending deliveries whose retry time has passed, or that were never picked up for `NOTIFICATION_STALE_AFTER_SECONDS`,
3. dead-letters deliveries that have used all their tries.

Each delivery is its own task, so a slow or failing channel never holds up others. This also covers retries that could not be queued because the broker was down: the delivery stays `pending` with its `next_retry_at` and the next sweep picks it up.

Delivery is **at least once**: if a worker dies after the provider accepted a message but before the row said `sent`, the recovery sends it again. Providers that support an idempotency key can be given `delivery.id` for this.

## Retention

`purge_notification_ledger_task` runs daily at 03:30; `python manage.py purge_notification_ledger [--dry-run] [--batch-size N]` does it by hand. Rows are removed in batches. A delivery that is still `pending` is never removed.

| Setting | Default | Removes |
|---|---|---|
| `NOTIFICATION_ATTEMPT_RETENTION_DAYS` | 30 | attempt rows |
| `NOTIFICATION_DELIVERY_RETENTION_DAYS` | 90 | sent, opened, clicked and bounced deliveries (and their attempts) |
| `NOTIFICATION_FAILED_RETENTION_DAYS` | 180 | failed deliveries and dead letters |

`0` keeps that kind of row forever.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `NOTIFICATION_MAX_ATTEMPTS` | 3 | tries before a delivery is dead-lettered |
| `NOTIFICATION_CLAIM_LEASE_SECONDS` | 120 | how long a worker may hold a delivery before another may take over |
| `NOTIFICATION_STALE_AFTER_SECONDS` | 300 | age at which a pending delivery nobody picked up is queued again |
| `NOTIFICATION_RATE_LIMIT_MAX_DEFERRALS` | 5 | deferrals before a rate-limited delivery is given up on |
| `NOTIFICATION_RATE_LIMIT_DELAY_SECONDS` | 60 | wait for each deferral |

Keep the claim lease longer than the slowest channel call, or a slow-but-alive worker can be taken over.

## Looking at the ledger

```python
# why did this delivery fail, and what did the provider say?
delivery.attempts.values("attempt_number", "outcome", "status_code", "error_message", "duration_ms")

# what is stuck?
NotificationDelivery.objects.filter(status="pending", next_retry_at__lt=timezone.now())

# failure mix per channel over the last day
NotificationAttempt.objects.filter(started_at__gte=day_ago).values("delivery__channel", "outcome").annotate(n=Count("id"))
```

## Tests and limits

`backend/apps/notifications/tests/test_delivery_ledger.py` covers classification, the attempt log, idempotency and claims, rate limiting, deduplication (including a race), crash recovery end to end, retention, and what each channel reports.

Not covered by automated tests: a real broker and a real worker (the recovery path is tested by running the sweep and the task directly), and PostgreSQL (the tests run on SQLite; the conditional unique constraint is supported by both). The tracking-pixel and digest code paths are unchanged.
