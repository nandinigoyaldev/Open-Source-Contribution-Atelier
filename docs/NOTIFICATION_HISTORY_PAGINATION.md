# Notification history pagination

`GET /api/notifications/` continues to use the existing page-number contract when
called without cursor options: `count`, `next`, `previous`, and `results` remain
unchanged. Existing clients do not need to migrate.

For large histories, opt into forward-only keyset pagination:

```http
GET /api/notifications/?pagination=cursor&page_size=20
```

The authenticated response is:

```json
{
  "next": "https://example.invalid/api/notifications/?pagination=cursor&page_size=20&cursor=opaque-token",
  "previous": null,
  "next_cursor": "opaque-token",
  "results": []
}
```

The example illustrates the envelope; real `results` contain the existing
notification serializer objects. Follow `next` unchanged, or pass `next_cursor`
as the `cursor` query parameter. A cursor automatically selects cursor mode.
At the end of history, both `next` and `next_cursor` are `null`.

Cursor mode omits the expensive total `count` and does not support backward or
arbitrary numbered jumps. `page_size` defaults to 20 and is capped at 100;
non-integer or nonpositive values return HTTP 400 with a `page_size` error.
Malformed, altered, unsupported or another user's cursors return HTTP 400 with
a `cursor` error. Restart without a cursor after such an error. An empty cursor
is invalid; omit the parameter for the first request. Signing-key changes can
also require restarting. Tokens are signed rather than encrypted; clients must
treat them as opaque, and they contain no notification text.

Results use descending `(created_at, id)` ordering. New notifications inserted
ahead of the current boundary, including rows with the same timestamp and newer
IDs, cannot shift or duplicate subsequent pages. Deleting a boundary row does
not invalidate its cursor. This is a live keyset traversal, not a database
snapshot: backdated inserts or edits to ordering fields may affect later pages.
Every query still filters by the authenticated recipient; a cursor grants no
access to another user's notifications. The digest endpoint is unchanged.

Apply migration `notifications.0008_notification_cursor_index` before rollout.
It adds `(recipient, created_at DESC, id DESC)` to support ordered history reads.
For large PostgreSQL tables, schedule the normal index-build migration within
an appropriate maintenance window. Rolling back the application to legacy
pagination is compatible with the added index; migrate back to `0007` if the
index must also be removed.

Implementation uses Django signing and DRF's custom pagination interface:
[Django signing](https://docs.djangoproject.com/en/5.0/topics/signing/),
[DRF pagination](https://www.django-rest-framework.org/api-guide/pagination/).
