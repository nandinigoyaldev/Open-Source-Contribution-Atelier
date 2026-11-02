# Open Source Contribution Atelier - API Versioning & Usage Guide

This guide describes the API versioning strategy, negotiation mechanisms, deprecation lifecycle, and developer guidelines for the Open Source Contribution Atelier REST API.

---

## 1. Overview

To support iterative feature development without breaking existing integrations, all API endpoints under `/api/` implement strict **API Versioning**. 

The current stable API version is **`1.0`**.

---

## 2. Version Negotiation Mechanisms

Clients can specify the desired API version using either **Accept Header Negotiation** (recommended) or **URL Prefix Fallback**.

### A. Accept Header Negotiation (Recommended)

Clients request a specific API version by providing the `version` parameter in the HTTP `Accept` header.

```http
GET /api/content/lessons/ HTTP/1.1
Host: localhost:8000
Accept: application/json; version=1.0
```

- **Supported Format**: `Accept: application/json; version=X.Y` (or `version=vX.Y`)
- **Example**: `Accept: application/json; version=1.0`

---

### B. URL Prefix Fallback

For simplified client integrations or browser debugging, versioned routes are accessible via explicit version URL prefixes under `/api/v1/`.

```http
GET /api/v1/content/lessons/ HTTP/1.1
Host: localhost:8000
Accept: application/json
```

---

### C. Unversioned Request Handling & Deprecation Notice

Requests sent directly to `/api/*` without a `version` parameter in the `Accept` header or a URL version prefix will:
1. Fall back to the default API version (`1.0`).
2. Include an explicit deprecation warning response header:

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-API-Deprecation: This endpoint will require a version header after 90 days
```

> [!WARNING]
> Unversioned requests will require an explicit version header after the 90-day transition grace period.

---

### D. Invalid Version Requests (`406 Not Acceptable`)

If a client requests an unsupported or invalid API version, the server returns an `HTTP 406 Not Acceptable` response with error details:

```http
HTTP/1.1 406 Not Acceptable
Content-Type: application/json

{
  "error": "Unsupported API version",
  "detail": "Invalid API version '99.0'. Supported versions are: 1.0.",
  "supported_versions": ["1.0"]
}
```

---

## 3. Version Discovery Endpoint

Clients and integration tools can query available API versions, lifecycle statuses, and changelog URLs dynamically via the discovery endpoint.

- **Endpoint**: `GET /api/versions/` (or `GET /api/v1/versions/`)
- **Authentication**: Unauthenticated / Public

### Example Response:

```json
{
  "default_version": "1.0",
  "versions": [
    {
      "version": "1.0",
      "status": "stable",
      "changelog_url": "/docs/changelog/v1.0",
      "sunset": null,
      "deprecation": null
    }
  ]
}
```

---

## 4. Endpoint Deprecation and Sunset Policy

When an API version or endpoint is scheduled for removal, standard RFC deprecation response headers are attached to all responses for that version:

| Response Header | Description | Standard |
| :--- | :--- | :--- |
| `X-API-Deprecation` | Warning header for unversioned fallback requests | Custom Header |
| `Deprecation` | Date or boolean indicating when the feature was deprecated | RFC 9261 |
| `Sunset` | HTTP-date indicating when the endpoint will be permanently retired | RFC 8594 |

---

## 5. Developer Guide: Adding or Deprecating API Versions

### Adding a New Version
1. Update `ALLOWED_API_VERSIONS` in `backend/config/settings.py`:
   ```python
   ALLOWED_API_VERSIONS = ["1.0", "2.0"]
   ```
2. Define version discovery entry in `API_VERSION_DISCOVERY`:
   ```python
   API_VERSION_DISCOVERY = {
       "1.0": {"status": "deprecated", "changelog_url": "/docs/changelog/v1.0"},
       "2.0": {"status": "stable", "changelog_url": "/docs/changelog/v2.0"},
   }
   ```
3. Update `backend/config/urls.py` to route `/api/v2/` patterns using `VersionedAPIRouter` or `api_v2_patterns`.

### Marking a Version as Deprecated
Add deprecation dates to `DEPRECATED_API_VERSIONS` in `backend/config/settings.py`:

```python
DEPRECATED_API_VERSIONS = {
    "1.0": {
        "deprecation": "@1700000000",
        "sunset": "Wed, 31 Dec 2026 23:59:59 GMT",
    }
}
```

---

## 6. Endpoints Reference

### A. Notes Export

Export user-authored notes across completed or in-progress lessons as structured Markdown or JSON.

- **Endpoint**: `GET /api/progress/notes/export/`
- **Authentication**: Required (`Token <token>` or Session)
- **Permissions**: Authenticated users only
- **Query Parameters**:
  - `format` (string, optional): Output format. Choices: `markdown` / `md` (default), `json`.
  - `limit` (integer, optional): Maximum notes to export (1–1000, default: `1000`).
  - `start_date` (string, optional): Inclusive filter starting on creation date (`YYYY-MM-DD`).
  - `end_date` (string, optional): Inclusive filter ending on creation date (`YYYY-MM-DD`). Note: Max date range span is 365 days.

#### Example Request:
```http
GET /api/progress/notes/export/?format=json&start_date=2026-01-01&end_date=2026-06-30 HTTP/1.1
Host: localhost:8000
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
Accept: application/json; version=1.0
```

#### Example JSON Response (`200 OK`):
```json
{
  "username": "johndoe",
  "email": "johndoe@example.com",
  "exported_at": "2026-08-16T12:00:00.000000",
  "total_notes": 2,
  "notes": [
    {
      "id": 14,
      "lesson_id": 3,
      "lesson_title": "Interactive Git Rebase",
      "lesson_slug": "interactive-git-rebase",
      "module_title": "Advanced Git Workflows",
      "content": "Remember to use git rebase -i HEAD~3 to squash exploratory commits.",
      "tags": ["git", "rebase"],
      "created_at": "2026-02-15T14:30:00Z",
      "updated_at": "2026-02-15T14:35:00Z"
    }
  ]
}
```

#### Example Markdown Response (`200 OK`):
- `Content-Type`: `text/markdown; charset=utf-8`
- `Content-Disposition`: `attachment; filename="notes_export_johndoe_20260816_120000.md"`

---

### B. Activity Heatmap CSV Export

Export granular daily learning activity data as a CSV file for offline analytics or personal tracking.

- **Endpoint**: `GET /api/progress/activity/export/` (alias: `GET /api/progress/heatmap/export/`)
- **Authentication**: Required (`Token <token>` or Session)
- **Permissions**: Authenticated users only
- **Query Parameters**:
  - `start_date` (string, optional): Filter records starting on date (`YYYY-MM-DD`).
  - `end_date` (string, optional): Filter records ending on date (`YYYY-MM-DD`).

#### Example Request:
```http
GET /api/progress/activity/export/?start_date=2026-01-01&end_date=2026-06-30 HTTP/1.1
Host: localhost:8000
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
Accept: application/json; version=1.0
```

#### Example Response (`200 OK`):
- `Content-Type`: `text/csv; charset=utf-8`
- `Content-Disposition`: `attachment; filename="activity_heatmap_20260101_20260630.csv"`

```csv
Date,Lessons Completed,XP Earned,Active Minutes
2026-01-10,3,150,45
2026-01-11,1,50,20
```

---

### C. Notification Preferences

Retrieve and update user delivery channel preferences and weekly progress digest subscription settings.

- **Endpoint**: `GET /api/notifications/prefs/` | `PUT /api/notifications/prefs/`
- **Authentication**: Required (`Token <token>` or Session)
- **Permissions**: Authenticated users only

#### GET Request Example:
```http
GET /api/notifications/prefs/ HTTP/1.1
Host: localhost:8000
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
Accept: application/json; version=1.0
```

#### GET Response Example (`200 OK`):
```json
{
  "email": true,
  "in_app": true,
  "websocket": true,
  "receive_weekly_digest": true,
  "weekly_digest": true
}
```

#### PUT Request Example:
```http
PUT /api/notifications/prefs/ HTTP/1.1
Host: localhost:8000
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
Content-Type: application/json
Accept: application/json; version=1.0

{
  "email": true,
  "in_app": true,
  "websocket": false,
  "receive_weekly_digest": false
}
```

#### PUT Response Example (`200 OK`):
```json
{
  "email": true,
  "in_app": true,
  "websocket": false,
  "receive_weekly_digest": false,
  "weekly_digest": false
}
```

---

### D. Bulk Lesson Import (CSV)

Upload and bulk-import lesson records into curriculum content from a UTF-8 encoded CSV file. Automatically handles slug creation, collision suffixing, and organization tenancy.

- **Endpoint**: `POST /api/content/published-lessons/bulk-import/`
- **Authentication**: Required (`Token <token>` or Session)
- **Permissions**: Authenticated users (Staff / `create_content` permission)
- **Request Format**: `multipart/form-data`
- **Form Fields**:
  - `file` (binary, required): UTF-8 CSV file containing lesson definitions.

#### Supported CSV Headers:
- `title` / `Title` (required)
- `summary` / `Summary` (optional)
- `content` / `Content` (optional)
- `difficulty` / `Difficulty` (`beginner` | `intermediate` | `advanced`, default: `beginner`)
- `category` / `Category` (default: `general`)
- `estimated_minutes` / `Estimated Minutes` (integer, default: `15`)
- `slug` / `Slug` (optional, auto-derived from title if omitted)

#### Example Request:
```http
POST /api/content/published-lessons/bulk-import/ HTTP/1.1
Host: localhost:8000
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="new_lessons.csv"
Content-Type: text/csv

title,summary,content,difficulty,category,estimated_minutes
"Git Stashing Deep Dive","Learn git stash save and pop","Detailed markdown content...","intermediate","git",20
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

#### Example Success Response (`201 Created` or `200 OK`):
```json
{
  "imported_count": 1,
  "imported_lessons": [
    {
      "id": 88,
      "slug": "git-stashing-deep-dive",
      "title": "Git Stashing Deep Dive",
      "category": "git",
      "difficulty": "intermediate",
      "estimated_minutes": 20
    }
  ],
  "errors": []
}
```

### E. Learning Activity Timeline

`GET /api/progress/activity/` (authenticated). The signed-in learner's own activity, newest first: lessons
completed, quiz questions answered, certificates issued and badges earned. Read-only.

| Query parameter | Meaning |
| --- | --- |
| `type` | Only these types: `lesson_completed`, `quiz_attempt`, `certificate_issued`, `badge_earned`. Repeat the parameter or separate with commas. Omit for every type. An unknown type is a `400`. |
| `limit` | Page size, 1 to 100 (default 20). A larger value is capped; zero, negative or non-numeric is a `400`. |
| `cursor` | The `next_cursor` of the previous page. An invalid cursor is a `400`. |

```json
{
  "results": [
    {
      "id": "lesson_completed:12",
      "type": "lesson_completed",
      "occurred_at": "2026-10-27T09:30:00+00:00",
      "title": "Git basics",
      "description": "Score 80",
      "metadata": { "lesson_slug": "git-basics", "score": 80 }
    }
  ],
  "next_cursor": "WyIyMDI2LTEwLTI3VDA5OjMwOjAwKzAwOjAwIiwibGVzc29uX2NvbXBsZXRlZCIsMTJd",
  "has_more": true,
  "limit": 20,
  "types": ["lesson_completed", "quiz_attempt", "certificate_issued", "badge_earned"]
}
```

* `id` is `"<type>:<primary key>"`: unique and stable, safe to use as a list key.
* Pagination is keyset based. The cursor is opaque; pass it back unchanged. Pages stay stable when new
  activity arrives, and cost does not grow with the length of the history (one query per type).
* Items with the same timestamp are ordered by type and id, so none is skipped or repeated.
* An empty history is `200` with `"results": []`, `"has_more": false` and `"next_cursor": null`.
* A completed lesson is dated by its last update, because lesson progress stores no separate completion time.

The frontend page is `/activity` ("My activity" in the side navigation).
