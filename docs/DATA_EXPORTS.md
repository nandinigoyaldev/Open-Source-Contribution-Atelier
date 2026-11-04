# Resumable Data Exports

A pipeline for exporting large datasets: bounded memory, checkpointed progress, resume after a worker restart, cancellation, and cleanup of abandoned jobs. Code: `backend/apps/data_exports/`. (The GDPR export in `docs/EXPORT.md` is a separate, single-request export of everything about a user.)

## Using it

| Request | Does |
|---|---|
| `GET /api/exports/` | the datasets and formats on offer, and your last 50 exports |
| `POST /api/exports/` `{"dataset": "notifications", "format": "csv"}` | starts an export, answers `202` with the job |
| `GET /api/exports/<id>/` | status and progress |
| `POST /api/exports/<id>/cancel/` | cancels a queued or running export |
| `GET /api/exports/<id>/download/` | the file; supports `Range` so an interrupted download can resume |

Datasets: `notifications`, `lesson_progress`, `quiz_attempts`, `code_submissions`, `sandbox_logs`. Formats: `csv` (UTF-8, header row, CRLF) and `ndjson` (one JSON object per line). Users can only ever export their own rows. A user can have `EXPORT_MAX_ACTIVE_PER_USER` (2) exports queued or running at once; more get `429`.

Job statuses: `queued` -> `running` -> `completed` (downloadable until `expires_at`, then `expired`), or `failed` / `cancelled`. `progress_percent` is an estimate against the row count when the job was created.

CSV cells that start with `=`, `+`, `-` or `@` are prefixed with `'` so a spreadsheet does not run user-supplied text as a formula.

## How it keeps memory bounded

Rows are read `EXPORT_CHUNK_ROWS` (1000) at a time with keyset paging (`WHERE pk > last_pk ORDER BY pk LIMIT n`) and appended to the file, which is flushed and `fsync`ed after every chunk. Nothing but one chunk is ever held in memory, and a queue worker never builds the whole file. Downloads are streamed from disk in 64 KB blocks. An export larger than `EXPORT_MAX_BYTES` (512 MB) fails rather than filling the disk.

Keyset paging is also what makes resuming possible: "continue after primary key N" stays correct if rows were added or deleted in the meantime, which `OFFSET` paging does not.

## Checkpoints and resuming

The job row holds `checkpoint = {last_pk, rows, bytes}`, written only *after* a chunk is safely on disk. On every start the part file (`<id>.part`) is cut back to exactly `bytes`, and reading continues at `pk > last_pk`. The finished file is therefore identical, byte for byte, to what an uninterrupted run produces, whatever the moment the worker died:

| The worker died... | What the next run does |
|---|---|
| mid-chunk, or after writing a chunk but before saving its checkpoint | cuts the unconfirmed tail off the file and re-reads that chunk |
| right after saving a checkpoint | continues from it |
| after writing everything, before renaming the file | finds the part file complete and finishes |
| after renaming, before saying `completed` | sees the finished file (its size matches the checkpoint) and marks it `completed` |
| and the file is missing, shorter than the checkpoint, or a finished file has the wrong size | starts over from the beginning |

The tests kill the job at every checkpoint (before and after it is saved) and at both ends of the rename, for both formats, and compare the result with an uninterrupted export.

## Who may run a job (leases)

A worker claims a job with one conditional `UPDATE` that stores a random `lease_token` and a heartbeat; every checkpoint refreshes the heartbeat and is written only if the token still matches. A worker whose lease was taken (it was slow, or the sweep gave the job to another worker) stops at its next write without changing anything. A `running` job with no heartbeat for `EXPORT_LEASE_SECONDS` (300) can be claimed by another worker.

## Retry semantics

* **Transient errors** (database connection trouble, I/O errors, timeouts): the job goes back to `queued` with a backoff (60 s, 120 s, ...), **keeping its file and checkpoint**, and the next attempt resumes from there.
* **Permanent errors** (unknown dataset, file too large, bad data): the job is `failed` at once and its files are removed.
* A worker that dies counts as an attempt too. After `EXPORT_MAX_ATTEMPTS` (3) attempts the job is `failed` ("Gave up after repeated worker failures").
* Running `run_export_job` again for a finished job does nothing, so a re-delivered task is harmless.

## Cancellation

`POST .../cancel/` on a queued job cancels it immediately. On a running job it sets `cancel_requested`; the worker checks it before every chunk, stops, deletes the part file and marks the job `cancelled`. At most one chunk of extra work is done.

## Cleanup

`sweep_exports` (Celery beat, every 2 minutes) does the housekeeping:

* running jobs without a heartbeat go back to the queue (or fail when out of attempts);
* queued jobs that are due, or that nobody picked up, are queued again; a cancel request on a job that never started is applied;
* completed exports are deleted after `EXPORT_TTL_HOURS` (24) and marked `expired`;
* files of failed, cancelled and expired jobs are removed;
* files that belong to no job are removed once they are a day old. Only files whose names look like `<uuid>.part|csv|ndjson` are ever touched.

## Settings

| Setting | Default | |
|---|---|---|
| `EXPORT_ROOT` | `backend/export_files` | where files are written; keep it private and never serve it directly |
| `EXPORT_CHUNK_ROWS` | 1000 | rows per step (the memory bound) |
| `EXPORT_MAX_ATTEMPTS` | 3 | tries per job |
| `EXPORT_LEASE_SECONDS` | 300 | silence after which a worker is presumed dead |
| `EXPORT_MAX_BYTES` | 536870912 | largest export file |
| `EXPORT_TTL_HOURS` | 24 | download window |
| `EXPORT_MAX_ACTIVE_PER_USER` | 2 | concurrent exports per user |

## Adding a dataset

```python
from apps.data_exports.datasets import register_dataset

register_dataset("my_things", "My things", "myapp.Thing", owner_field="user")
```

The model needs an integer primary key and a field pointing at the owning user. Use `exclude=("secret_field",)` to leave columns out. Registration for the built-in datasets is in `register_default_datasets()`.

## Limits

* Files live on the local disk of the worker. With separate web and worker hosts, `EXPORT_ROOT` must be shared storage; an object-store backend is not included.
* The ledger of an export is its row; there is no audit-log entry per download.
* Tested on SQLite with a mocked queue. The worker-restart tests simulate a killed worker by raising `KeyboardInterrupt` inside the pipeline; they do not run a real Celery worker.
