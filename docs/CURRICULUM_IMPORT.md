# Bulk curriculum import

Import a whole curriculum (modules, lessons, prerequisites) from one zip
archive. The archive is validated first and nothing is written until an admin
publishes it. Publishing runs in a single database transaction, so a failure
leaves the existing curriculum exactly as it was.

## Archive format

```
curriculum.zip
  manifest.json          required
  quizzes.json           optional quiz bank (id -> quiz)
  module-1/what-is-git.md
  module-1/first-commit.md
  module-2/branches.md
```

`manifest.json` mirrors `frontend/public/content/curriculum.json`:

```json
{
  "format_version": 1,
  "modules": [
    {
      "id": "module-1",
      "title": "Getting Started",
      "description": "Optional.",
      "lessons": [
        {
          "slug": "sample-first-commit",
          "title": "Your First Commit",
          "description": "Used as the lesson summary.",
          "difficulty": "beginner",
          "estimatedMinutes": 8,
          "filePath": "module-1/first-commit.md",
          "prerequisites": ["sample-what-is-git"],
          "quizzes": ["commit-basics"]
        }
      ]
    }
  ]
}
```

| Field | Rules |
| --- | --- |
| `format_version` | Optional, must be `1`. |
| module `id`, `title` | Required. Ids must be unique. The module title becomes the lesson `category`. |
| lesson `slug` | Required, lowercase words joined by `-`, unique in the archive. |
| lesson `title`, `filePath` | Required. `filePath` is a relative path of a markdown file inside the zip (no `..`, no absolute paths, one lesson per file). |
| `difficulty` | `beginner` (default), `intermediate` or `advanced`. |
| `estimatedMinutes` | Integer 1-120 (default 15). |
| `prerequisites` | Slugs of other lessons in the same archive (forward references are fine). |
| `quizzes` | Ids from `quizzes.json` or inline `{question, options, answer, explanation}` objects. |

A lesson file may start with a simple front matter block (`key: value` lines
between two `---` lines). It is stripped from the stored lesson body.
Lesson order follows manifest order.

## What the validator checks

Before anything is written, `apps/content/services/curriculum_import.py`
reports:

* unreadable archives, missing or invalid `manifest.json`, too many entries or
  too large an expanded size, lessons over 1 MiB
* duplicate module ids, duplicate or malformed slugs, duplicate `filePath`s
* missing references: prerequisites, quiz ids, lesson files, and internal
  markdown links (`/lessons/<slug>` or relative files inside the archive)
* unsafe paths (`..`, absolute, backslashes) and unsafe URLs (any scheme other
  than `http`, `https`, `mailto`, e.g. `javascript:`, `data:`, in markdown
  links, images and `href`/`src` attributes; code spans and fences are ignored)
* malformed or unclosed front matter, empty lessons, invalid UTF-8
* bad inline quizzes, difficulty and minutes

The front matter, link and quiz checks are the ones from
`scripts/validate_curriculum.py`, applied to a zip instead of a directory.

## Lifecycle

```
validating -> previewed -> publishing -> published
      \-----------\-------------\-----> failed
```

* `validating`: lessons are validated in chunks (`CURRICULUM_IMPORT_CHUNK_SIZE`,
  default 25). After each chunk the import row stores `cursor` and the partial
  report, so if the worker dies the same task resumes at the first unfinished
  chunk instead of starting over.
* `previewed`: no problems found. `report.plan` lists which lesson slugs would
  be created, updated or are unchanged.
* `publishing`: lessons are upserted by slug inside one transaction;
  prerequisites are set once every lesson exists. Lessons not in the archive
  are never deleted. An import that was interrupted in `publishing` can be
  published again.
* `published`: `report.published` holds the created/updated/unchanged counts.
  Importing the same archive again changes nothing (all lessons unchanged).
* `failed`: validation problems (listed in `report.problems`, capped at 500 with
  `problem_count` giving the real total) or a publish error (rolled back,
  `report.publish_error`).

The stored archive's SHA-256 is checked again before publishing, so only the
archive that was validated can be published.

Quizzes are validated and counted, but the published `Lesson` table has no
quiz storage, so they are not written anywhere yet.

## Admin API

All endpoints need an admin (`is_staff`) user.

| Method and path | Purpose |
| --- | --- |
| `POST /api/content/curriculum-imports/` | Multipart upload, field `archive`. Starts validation. |
| `GET /api/content/curriculum-imports/` | List imports. |
| `GET /api/content/curriculum-imports/{id}/` | Status, cursor and report (the preview). |
| `POST /api/content/curriculum-imports/{id}/publish/` | Publish a `previewed` import (409 otherwise). |

Work is sent to Celery (`apps.content.tasks.validate_curriculum_import`,
`publish_curriculum_import`). If no Celery broker answers, it falls back to
Django-Q (`manage.py qcluster`). `CURRICULUM_IMPORT_MAX_ARCHIVE_BYTES`
(default 50 MiB) caps uploads.

## Management command

```bash
python manage.py import_curriculum start path/to/curriculum.zip   # validate + report
python manage.py import_curriculum preview 12
python manage.py import_curriculum publish 12
python manage.py import_curriculum start path/to/curriculum.zip --publish
python manage.py import_curriculum --format json preview 12
```

The command runs in-process (no worker needed) and exits non-zero when
validation or publishing fails.

To build an archive from a content directory:

```bash
cd my-content && python -m zipfile -c ../curriculum.zip manifest.json quizzes.json module-1 module-2
```

A small working example lives in
`backend/apps/content/tests/fixtures/curriculum_import/sample/`.
