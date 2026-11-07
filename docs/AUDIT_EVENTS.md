# Admin Audit Events

Admin actions write a structured audit event so that "who changed this, and when" can be answered while troubleshooting. This page covers the event shape, which actions emit events, what is never stored, who can read events, and how long they are kept.

## 1. Event Shape

Events are rows in the existing `AuditEvent` table (`backend/apps/audit/models.py`). No new model was added. They are written with `record_admin_event()` from `backend/apps/audit/admin_events.py`.

| Field | Stored in | Meaning |
| --- | --- | --- |
| actor | `actor` | The authenticated user who did it. `null` if there was none. |
| operation | `extra["operation"]` | The specific action, e.g. `issue.updated`. |
| action | `action` | Coarse verb: `created`, `updated` or `deleted`. |
| target type | `resource_type` | `app_label.model_name` of the thing acted on. |
| target id | `resource_id` | Primary key of the target, as a string. |
| timestamp | `created_at` | When the event was written (UTC). |
| request id | `correlation_id` | The `X-Request-ID` of the request. It is sent back in the response header too, so a support ticket can quote it. |
| payload | `extra["payload"]` | Small dict describing the change, already redacted. |
| summary | `extra["summary"]` | One line for the admin list view. |

`extra["source"]` is always `"admin_action"` for these events, which separates them from the row-level events that `signals.py` writes for every `AuditableModel` save.

`action` is a `varchar(10)` limited to the three verbs, so the specific operation name lives in `extra` instead of a new column.

Example event as returned by `GET /api/admin/audit/<id>/` (trimmed):

```json
{
  "id": 42,
  "actor_username": "staff",
  "action": "updated",
  "resource_type": "issues.issuereport",
  "resource_id": "7",
  "correlation_id": "5c1f0a8e-5c6c-4a43-9a3e-0d8f7d4a9b21",
  "created_at": "2026-10-26T09:11:13Z",
  "extra": {
    "source": "admin_action",
    "operation": "issue.updated",
    "summary": "Updated issue report #7",
    "payload": {"changes": {"status": {"from": "Open", "to": "Resolved"}}}
  }
}
```

## 2. Actions That Emit Events

| Operation | Action | Target | Where | Payload |
| --- | --- | --- | --- | --- |
| `issue.updated` | `updated` | `issues.issuereport` | `PATCH/PUT /api/issues/<id>/` | Per changed field. Old and new value for `title`, `status`, `issue_type`, `is_verified`. For any other field (`description`, `url_path`, `image`) only `{"changed": true}`. |
| `issue.deleted` | `deleted` | `issues.issuereport` | `DELETE /api/issues/<id>/` | `title`, `status`, `issue_type` of the deleted report. |
| `user.role_assigned` | `created` | `auth.user` (the user who got the role) | `POST /api/rbac/assign/` | `role_id`, `role_name`, `organization_id`. |
| `user.role_revoked` | `deleted` | `auth.user` | `POST /api/rbac/revoke/` | `role_id`, `role_name`, `organization_id`. |
| `billing.reconcile_run` | `created` | `billing.reconciliation` (the run id) | `reconcile_billing` command, dry run or `--apply` | `dry_run`, counts, and the mismatches found. |
| `billing.reconcile_repair` | `created` or `updated` | `billing.customersubscription` or `billing.invoice` | `reconcile_billing --apply` | `run_id`, `kind`, Stripe ids, and the local and Stripe value of each changed field. |

Notes:

- An event is written only after the action succeeded. A request that is rejected (403, 404, validation error) writes nothing.
- Assigning a role the user already has changes nothing, so it writes nothing.
- The older `rbac.AuditLog` rows are still written as before. The new events are in addition to them, not a replacement.
- Reconcile events have no actor because a command has no user. `correlation_id` is the run id, so `?correlation_id=<run id>` lists a run and its repairs together. See [STRIPE_WEBHOOK_LEDGER.md](STRIPE_WEBHOOK_LEDGER.md).

Filter admin events in the API with `?operation=issue.updated`, `?resource_type=issuereport`, `?resource_id=7`, `?actor=<username or id>` or `?correlation_id=<request id>`.

### Adding another admin action

```python
from apps.audit.admin_events import record_admin_event, target_type_for

record_admin_event(
    operation="thing.archived",
    action="updated",
    target_type=target_type_for(thing),
    target_id=thing.pk,
    request=request,                      # gives actor and request id
    payload={"reason": reason},           # redacted for you
    summary=f"Archived thing #{thing.pk}",
)
```

Call it after the change has succeeded. It never raises. If the write fails it logs the error on the `apps.audit.admin_events` logger and returns `None`, so an audit problem cannot turn a successful admin action into a 500. Use a value like `thing.archived`, not free text, for `operation`, because it is what people filter on.

### Password reset events

The signed-out reset flow writes to the same table through `record_security_event()` (`backend/apps/audit/security_events.py`). Nobody is signed in, so `actor` is `null`, the account is the target, and `ip_address` and `user_agent` are kept: they are the only way to connect repeated attempts. The address comes from the same proxy-aware lookup the rate limits use. `extra["source"]` is `"security"`.

| Operation | Action | Target | When | Payload |
| --- | --- | --- | --- | --- |
| `password_reset.requested` | `created` | `auth.user`, or `unknown` when no account matched | The worker handled a valid request. | `account_found`. For an unknown address also `email_fingerprint`. |
| `password_reset.suppressed` | `created` | `auth.user` | The account already reached `PASSWORD_RESET_MAX_PER_HOUR`, so no token or email was created. | `recent_requests`. |
| `password_reset.completed` | `updated` | `auth.user` | The password was changed with a reset token. | Empty. |
| `password_reset.failed` | `created` | `auth.user`, or `unknown` when no such token exists | A token was rejected at the validate or confirm step. | `stage` (`validate`, `confirm`), `reason` (`unknown_token`, `expired_token`, `used_token`). |
| `password_reset.rate_limited` | `created` | `unknown` | A rate limit blocked a caller. Written once per address and stage every 15 minutes, so a flood does not become a flood of rows. | `stage`, and `email_fingerprint` on the request step. |

Notes:

- Tokens are never recorded. Neither is an address that may not belong to anyone: `email_fingerprint` is a short keyed hash, so repeats for one address can be grouped without storing it.
- `reason` is more exact than the response. The caller only sees `invalid_token` or `expired_token`.
- A `used_token` failure is worth a look, since it means a link was tried again after it was spent.

Find them with `?operation=password_reset.failed`, or `?resource_type=auth.user&resource_id=<id>` for one account.

## 3. What Is Never Stored

- **Secrets.** `redact()` (`backend/apps/audit/redaction.py`) runs on every payload and summary before they are saved. It replaces with `[REDACTED]`:
  - the value of any key whose name contains `password`, `passwd`, `passphrase`, `secret`, `token`, `authorization`, `apikey` / `api_key` / `api-key`, `cookie`, `credential`, `privatekey`, `csrf` or `sessionid`, or is exactly `key`, `auth`, `pwd`, `otp`, `jwt` or `signature`. This applies at any depth in nested dicts and lists.
  - string values that look like a credential even under an ordinary key: JWTs, `Bearer ...` / `Basic ...` values, GitHub, OpenAI-style, AWS and Slack token prefixes, PEM private key blocks, inline `password=...` or `api_key: ...` pairs, and any unbroken 32+ character string of letters and digits.
- **Free text.** Issue descriptions, URLs and uploaded images are user supplied, so events only record that they changed.
- **Whole request bodies and headers.** Payloads are built by hand from named fields, never copied from `request.data` or `request.META`.
- **Client details.** `ip_address` and `user_agent` are left empty for admin events. Password reset events keep them, see above.
- Strings in a payload are cut at 500 characters and structures deeper than 8 levels are cut off.

Redaction errs on the side of hiding too much. A field named `tokens_used` or a 40 character commit hash will be replaced. UUIDs, which are used for request ids, are kept.

Redaction is pattern based and cannot catch every secret. A secret that is short, has no recognisable prefix and sits under an innocent key will get through, which is why the payloads are kept small and mostly limited to enum-like fields.

The row-level events written by `signals.py` (`before` / `after` model snapshots) are separate and are not redacted by this change.

## 4. Who Can Read Events

- `GET /api/admin/audit/` and `GET /api/audit/` (list, filters, CSV and JSON export): staff users only (`IsAdminUser`).
  - Export: add `export=csv` or `export=json` to the same filters. The file is streamed row by row (rows are read with `iterator()`, nothing is built up in memory), it is not limited to one page, and an empty result is a CSV with only the header row or `[]`. Any other `export` value is a `400`. Text cells that start with `=`, `+`, `-` or `@` get a leading `'` so a spreadsheet does not run them as formulas.
- `GET /api/admin/audit/<id>/` and `GET /api/audit/<id>/`: staff users only. This used to accept any logged-in user and now matches the list endpoint.
- Django admin: the `Audit Trail` app is read only (add, change and delete are switched off in `admin.py`), so only staff with the view permission can look at events there.
- Nobody can edit or delete an event through the application. `AuditEvent.save()` refuses to update an existing row and `delete()` always raises. The only thing that removes rows is the archive task below.
- Database access is outside the application. Restrict it to people who already need production access, and ideally give the app a database role that can `INSERT` and `SELECT` on the audit table but not `UPDATE` or `DELETE`.

CSV and JSON exports and the archive files below contain the same data as the API, so treat them with the same care.

### Filtering and paging the list

`GET /api/admin/audit/` filters on the server and pages the result. Filters combine with AND.

| Parameter | Meaning |
|---|---|
| `start_date`, `end_date` | Date range. `YYYY-MM-DD` or an ISO 8601 date-time. A date without a time covers the whole day, so `end_date=2026-01-31` includes everything on the 31st. A date-time is used exactly as given. Plain dates are read in the server's time zone. |
| `actor` | A user id, or part of a username. |
| `action` | One of `created`, `updated`, `deleted`. |
| `operation` | The named admin event in `extra`, e.g. `issue.updated` (exact match). |
| `resource_type` (or `model_type`) | Part of the `app_label.model_name` of the target. |
| `resource_id`, `correlation_id` | Exact match. |
| `search` (or `q`) | Text search over resource, id, actor, correlation id and user agent. |
| `page`, `page_size` | Page number (from 1) and size. Default 20, at most 100; a bad `page_size` falls back to the default. A page past the last one is a `404`. |

The response carries `count`, the number of events matching the filters (not the page size), plus `next` and `previous`, which keep the filters.

A value the server cannot use is a `400` that names the field, instead of being ignored: an impossible date such as `2026-02-30`,
a start date after the end date, an `action` that is not one of the three verbs, or a text filter over 100 characters. CSV and JSON
export (`export=csv|json`) use the same filters and return every matching event, not just one page. In the admin screen the filter
inputs are checked in the browser first, and typing waits for a short pause before a request is sent.

## 5. Retention

- Events are kept in the database for `AUDIT_RETENTION_DAYS` (default `90`, set by environment variable).
- A daily scheduled job (`audit-events-archive-daily`, running `apps.audit.tasks.archive_audit_events`) writes events older than that to a JSON file in `AUDIT_ARCHIVE_DIR` (default `backend/archives/audit/`) and then deletes them from the table.
- Archive files are plain, unencrypted JSON on the server's disk. They hold already redacted payloads, but they still name actors and targets. Limit the directory to the application user, and apply your own retention to the files if you need to delete data after a fixed period. Nothing in the app removes archive files.
- Events whose actor account is deleted keep their row with `actor` set to `null`. The target id stays, since it is only a number.
- If you need a different period for compliance, change `AUDIT_RETENTION_DAYS` and decide separately how long archive files live.

## 6. File Inventory

```
backend/apps/audit/admin_events.py        # record_admin_event() and operation names
backend/apps/audit/security_events.py     # record_security_event(), used by password reset
backend/apps/audit/redaction.py           # redact()
backend/apps/audit/views.py               # read endpoints (staff only), ?operation filter
backend/apps/audit/tasks.py               # archive_audit_events (retention)
backend/apps/issues/views.py              # issue.updated, issue.deleted
backend/apps/rbac/views.py                # user.role_assigned, user.role_revoked
backend/apps/audit/test_admin_events.py   # redaction, shape, emission, access tests
docs/AUDIT_EVENTS.md                      # this document
```
