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

## Authentication Header Summary (Quick Reference)
```http
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

---

## Source of Truth
- `backend/apps/progress/views.py`
- `backend/apps/progress/serializers.py`
- `backend/apps/progress/tests.py`

