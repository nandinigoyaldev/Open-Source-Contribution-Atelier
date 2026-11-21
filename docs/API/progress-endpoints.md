# Progress App API — Endpoint Reference

This document describes the **Progress** app API endpoints related to:
- Leaderboard
- Daily stats
- Certificates (public verification + authenticated “my certificate”)

> Base path (typical): `/api/progress`

## Authentication (JWT)
Most endpoints require an authenticated user.

Use:
- `Authorization: Bearer <JWT_ACCESS_TOKEN>`

If you’re using DRF SimpleJWT, unauthenticated requests typically result in:
- `401 Unauthorized` (missing/invalid token)
- or `403 Forbidden` (authenticated but not allowed)

Public certificate verification allows no authentication.

---

## Leaderboard
### GET `/api/progress/leaderboard/`

**View:** `LeaderboardView`

**Permissions:** `IsAuthenticatedOrReadOnly`
- Anonymous users may access the leaderboard.
- Authenticated users also receive `personal_rank` when **no** username search is applied.

#### Query Parameters
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `time_period` | string | `all_time` | Time aggregation window used by the leaderboard service. |
| `username` | string | — | If provided, filters/suggests ranking for matching username(s). When `username` is provided, `personal_rank` is omitted. |
| `page` | integer | `1` | Page number (1-indexed). |
| `limit` | integer | `50` | Page size. |

#### Response (200)
```json
{
  "leaderboard": [
    // array entries returned by LeaderboardService
  ],
  "personal_rank": null,
  "page": 1,
  "limit": 50,
  "total_users": 1234,
  "total_pages": 25
}
```

**Fields**
- `leaderboard`: array of leaderboard rows returned by the backend service.
- `personal_rank`:
  - an integer rank for the authenticated user when `username` is **not** provided
  - otherwise `null`
- `page`, `limit`: echoed pagination params
- `total_users`: total users matched by the leaderboard service
- `total_pages`: computed from `total_users` and `limit`

#### Notes / Edge Cases
- If `username` is set, `personal_rank` is not computed.

#### Example Request
```http
GET /api/progress/leaderboard/?time_period=all_time&page=1&limit=20
Authorization: Bearer <token>
```

---

## Daily Lesson Stats
### GET `/api/progress/daily-stats/`

**View:** `DailyLessonStatsView`

**Permissions:** `IsAuthenticated`

#### Query Parameters
None.

#### Response (200)
Response is an array of day-grouped lesson completion stats.

`DailyProgressSerializer` shape:
- `date`: date (YYYY-MM-DD)
- `count`: integer number of completed lessons that day
- `lessons`: array of lesson titles completed that day

```json
[
  {
    "date": "2026-07-01",
    "count": 3,
    "lessons": ["Lesson 1", "Lesson 2", "Lesson 3"]
  }
]
```

#### Example Request
```http
GET /api/progress/daily-stats/
Authorization: Bearer <token>
```

---

## Certificates

### 1) Public Certificate Verification
#### GET `/api/progress/verify/<hash>/`

**View:** `CertificateVerificationView`

**Permissions:** `AllowAny`
- No authentication required.

#### Path Parameters
| Name | Type | Description |
|------|------|-------------|
| `hash` | string | Certificate `verification_hash` (stored as `Certificate.verification_hash`). |

#### Response (200)
```json
{
  "is_valid": true,
  "certificate": {
    "verification_hash": "<hash>",
    "course_name": "Open Source Contribution Course",
    "issued_at": "2026-07-10T12:34:56Z",
    "learner_name": "Test User",
    "is_active": true
  }
}
```

If certificate exists but is inactive (revoked/deactivated), the endpoint still returns HTTP **200**, with `is_valid=false`:
```json
{
  "is_valid": false,
  "error": "This certificate has been revoked or deactivated.",
  "certificate": {
    "verification_hash": "<hash>",
    "course_name": "Open Source Contribution Course",
    "issued_at": "2026-07-10T12:34:56Z",
    "learner_name": "Test User",
    "is_active": false
  }
}
```

#### Response (404)
When certificate does not exist:
```json
{
  "is_valid": false,
  "error": "Certificate not found or invalid hash."
}
```

#### Example Request
```http
GET /api/progress/verify/8f3a0d2c-.../
```

---

### 2) Authenticated: Get or Create My Certificate
#### GET `/api/progress/certificate/`

**View:** `MyCertificateView`

**Permissions:** `IsAuthenticated`

This endpoint either:
- Returns the user’s existing certificate, or
- Creates a certificate if the user has completed all lessons, or
- Returns 400 if the user is not yet eligible.

#### Response (200)
If the certificate already exists:
```json
{
  "has_certificate": true,
  "certificate": {
    "verification_hash": "<hash>",
    "course_name": "Open Source Contribution Course",
    "issued_at": "2026-07-10T12:34:56Z",
    "learner_name": "Test User",
    "is_active": true
  }
}
```

#### Response (201)
If eligible and the certificate is created for the first time:
```json
{
  "has_certificate": true,
  "certificate": {
    "verification_hash": "<hash>",
    "course_name": "Open Source Contribution Course",
    "issued_at": "2026-07-10T12:34:56Z",
    "learner_name": "Test User",
    "is_active": true
  }
}
```

#### Response (400)
Not eligible (e.g., not all lessons completed) or no lessons exist:
```json
{
  "has_certificate": false,
  "detail": "Course requirements not met. Complete all lessons to unlock."
}
```

#### Example Request
```http
GET /api/progress/certificate/
Authorization: Bearer <token>
```

---

## Writing Lesson Progress

`POST` or `PATCH /api/progress/me/`, `POST /api/progress/bulk-sync/` and `POST /api/progress/bulk-update/` all follow the same rule. Every progress row has a `version` that goes up by one on each applied write, and the list at `GET /api/progress/me/` returns it.

Send `expected_version` with the version you last read, or `0` if you saw no row for that lesson.

| You send | Row on the server | Result |
|---|---|---|
| `expected_version` that matches | any | Applied as sent, `version` goes up |
| `expected_version` that does not match | exists | Refused, conflict |
| no `expected_version` | exists, write moves it forward | Applied. `completed` never goes back to `false` and `score` never drops, so only the part that moves forward is kept |
| no `expected_version` | exists, write has nothing new | Refused, conflict |
| anything | already holds exactly what you sent | `200`, nothing changes |
| anything | no row yet | Created with `version` 1 |

`client_timestamp` is stored but does not decide anything, client clocks can't be trusted for ordering.

### Conflict on `/api/progress/me/` (409)

The body is the current row plus why the write was refused:

```json
{
  "id": 12,
  "user": 3,
  "lesson": 7,
  "lesson_slug": "git-basics",
  "completed": true,
  "score": 80,
  "attempt_count": 0,
  "version": 6,
  "updated_at": "2026-07-10T12:34:56Z",
  "code": "progress_version_conflict",
  "detail": "This lesson's progress changed since this client last read it.",
  "expected_version": 4
}
```

Show that state to the user. To overwrite it on purpose, send the same write again with `expected_version` set to the `version` from this body.

### Conflicts in bulk requests

Bulk requests answer `200` and commit the items that were accepted. Each refused item is listed in `conflicts` with the same fields as the 409 body, and it is not counted in `synced_count`, `progress_ids`, `updated_count` or `updated_ids`. `bulk-update` also returns `versions`, the current version by lesson slug for every item that was not refused.

---

## Bookmarks

`POST /api/progress/bookmarks/<slug>/` saves a lesson to Read Later: `201`, or `200` when it was already saved. `DELETE /api/progress/bookmarks/<slug>/` removes it: `204`, or `404` when there is nothing to remove.

Both take an `Idempotency-Key` header. A request that repeats a key gets the first answer back with `Idempotency-Replay: true` instead of being applied again, so a removal that is replayed after it already went through answers `204`, not `404`. The first `404` of a keyed removal is stored too, so a retry of it answers `404` again even if the lesson was saved from another device in between, and does not remove that newer bookmark. The frontend offline queue sends a new key per queued action.

`DELETE` also takes an optional `expected_id` query parameter, the `id` of the bookmark being removed as `GET /api/progress/bookmarks/` returned it. If the lesson's bookmark has another id now, it was saved again after the client read it (another tab or device) and the server answers `409` without deleting anything:

```json
{
  "code": "bookmark_conflict",
  "detail": "This lesson was bookmarked again after the client read it.",
  "lesson_slug": "git-basics",
  "bookmarked": true,
  "id": 42,
  "created_at": "2026-11-20T10:00:00+00:00"
}
```

To remove it on purpose, send the delete again with `expected_id` set to the `id` from this body, and use a new `Idempotency-Key` for it. The conflict answer is stored under the old key and `expected_id` is not part of what the key is compared on, so the old key would just get the `409` back. Keep the new key only for retries of this new delete. A value that is not a number is a `400`.

## Offline replay (frontend)

Writes made offline go into the `sync-queue` IndexedDB store (`frontend/src/lib/offlineQueue.ts`) and are replayed on reconnect, by the page and by the service worker:

- Each action gets a `seq` from a cursor kept in `localStorage` (`atelier_sync_cursor`) and the queue replays in `seq` order, not in key order. A newer action for the same lesson waits while an older one failed or is in conflict.
- Each action gets its own `Idempotency-Key` when it is queued and keeps it across retries.
- The page sends the access token it has at replay time, not the one saved when the action was queued. It reads that token once per request and checks its owner, and holds actions that were queued under another account (or when the owner of the token cannot be read).
- A result only settles the revision that was sent, found by its idempotency key. If a newer write for the same lesson replaced it while the request was out, the newer one stays queued.
- An action is marked as sent right before the request. A bookmark change that is reversed before that is cancelled; one that may already have reached the server is replaced by the opposite change instead.
- The service worker also marks actions as sent and settles only the revision it sent. It drops writes the server rejected for good (`400`, `404`, `410`, `422`, or a key the server will not accept) so they do not hold up later writes, stores a `409` conflict in the queue before telling the pages, and fails the background sync on temporary errors so the browser tries again.
- Records carry `schemaVersion`. Older records are upgraded when the queue is read. Records from a newer version are left alone.
- A `409` with a `code` is a conflict and goes to the conflict prompt. A `409` about the idempotency key (another replay is sending the same key) is retried later.

---

## Authentication Header Summary (Quick Reference)
```http
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

---

## Source of Truth
- `backend/apps/progress/views.py`
- `backend/apps/progress/serializers.py`
- `backend/apps/progress/tests.py`

