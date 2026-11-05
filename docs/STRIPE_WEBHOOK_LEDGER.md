# Stripe Webhook Ledger and Reconciliation

How a Stripe event is applied exactly once, what happens when events arrive late or out of order, and how to repair drift. Code: `backend/apps/billing/` (`webhooks.py`, `services.py`, `reconciliation.py`, `management/commands/reconcile_billing.py`).

## The ledger

`StripeEvent` has one row per Stripe event, unique on `event_id`. The row is inserted first, inside the same transaction as everything the event changes, and it gets its outcome at the end of that transaction.

- **Duplicate delivery:** the insert finds the row, nothing is applied, and the webhook answers 200.
- **Two workers on the same event:** the second insert waits on the unique index until the first commits, then finds the row and stops. If the first rolled back, the second applies the event.
- **Crash halfway:** the ledger row rolls back with the rest, the webhook answers 500, and Stripe's retry starts clean. An event can never be marked done without being applied.

The invoice PDF task is queued after the commit, so a rolled back event queues nothing and a worker can always see the invoice.

| Outcome | Meaning |
|---|---|
| `applied` | The event changed local state. |
| `stale` | Newer state was already saved, so the subscription was left alone. A late `invoice.payment_failed` still writes its invoice and payment rows, and a late `checkout.session.completed` still fills in links that are empty. |
| `unmatched` | No local row for it. `reconcile_billing` reports these when the customer is unknown. |
| `ignored` | An event type the webhook does not handle. |

Rows are kept, there is no purge job yet. Stripe stops retrying after three days, so anything older is only useful as history.

## Ordering

`CustomerSubscription.last_event_at` holds the Stripe `created` time of the newest event applied to the subscription the row follows. An event older than that is stale.

| Event | Rule |
|---|---|
| `customer.subscription.updated`, `invoice.payment_failed` | Applied only if not stale. |
| `customer.subscription.deleted` | Always applied to the subscription it names. Stripe never revives a canceled subscription, so it holds however late it lands. |
| `checkout.session.completed` | If stale, it only fills in an empty subscription id, customer id, plan or period end. The exception is a checkout for a different subscription on a canceled row: that is a new purchase and starts a new timeline. |
| `invoice.paid` | Not ordered, it does not touch the subscription. It settles an invoice a failed attempt left `open`, and a late failure cannot reopen a paid one. |

`created` is in whole seconds. On a tie the event applies, unless the row is canceled, so a cancellation wins against something from the same second.

A row that follows a live subscription ignores events for any other subscription of that customer, even when they are newer. Those events are `unmatched`. A row with no subscription yet, or a canceled one, takes the customer's next event and binds to its subscription.

## Signature and timestamp checks

`stripe.Webhook.construct_event` checks the signature and rejects a `t=` older than five minutes, so a captured request cannot be replayed later. A replay inside those five minutes stops at the ledger.

Stripe signs every retry again, so an event from three days ago arrives with a fresh `t=`. The age of the event itself is never limited: a late event is checked for order, not dropped.

## Reconciliation

```bash
python manage.py reconcile_billing                     # report only, the default
python manage.py reconcile_billing --apply             # repair
python manage.py reconcile_billing --customer cus_123  # one customer
python manage.py reconcile_billing --days 7 --json     # invoice window, machine readable report
```

It needs a real `STRIPE_SECRET_KEY` and refuses to run in mock mode. Run it by hand or from cron, nothing schedules it. Run the dry run first and read it: `--apply` trusts Stripe over the local rows. The exit code is 1 if a customer could not be checked or a repair failed. The others still run.

| Kind | Found when | `--apply` |
|---|---|---|
| `subscription_state` | Status, access, plan, period end, failed payment date or subscription id differ. This includes a live subscription on Stripe that the row never linked, which is what a lost checkout event looks like. | Copies Stripe's state and sets `last_event_at` to the time of the fetch, so an older event landing later is stale. Backs off if a newer event landed during the run. |
| `invoice_missing` | Paid on Stripe, no local invoice. | Creates the invoice and payment and queues the PDF. |
| `invoice_status` | The status differs. | Updates it, and adds the payment when it became paid. |
| `subscription_missing` | Stripe does not know the subscription id. | Reports only. Stripe keeps canceled subscriptions, so this means a wrong id or a key from the wrong account, not a cancellation. Revoking access on that is too risky. |
| `event_unmatched` | A ledger row in the window for a customer with no local row. | Reports only. |

### Audit trail

Every run writes one `billing.reconcile_run` audit event, a dry run too, with what it found. Dry runs write nothing else. Each repair writes a `billing.reconcile_repair` event in the same transaction as the repair, and if that write fails the repair rolls back. Both carry the run id in `correlation_id`, so you can compare a dry run with what `--apply` did later:

```text
GET /api/admin/audit/?correlation_id=<run id>
```

Stripe ids of 32 or more characters may show as `[REDACTED]` in these events, see [AUDIT_EVENTS.md](AUDIT_EVENTS.md). The target of a repair is the local row id, which is not affected.
