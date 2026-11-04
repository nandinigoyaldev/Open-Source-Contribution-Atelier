"""
The export pipeline: write a dataset to a file in bounded memory, checkpoint as it goes, and carry
on from the checkpoint after any interruption.

How resuming stays correct
--------------------------
The job row holds a checkpoint ``{last_pk, rows, bytes}`` that is only advanced *after* a chunk has
been written and fsynced. On every start the part file is cut back to ``bytes``, so whatever a dead
worker had half written after its last checkpoint is discarded, and reading restarts at
``pk > last_pk``. Whatever the moment the worker died, the finished file is byte-for-byte what an
uninterrupted run would have produced.

Only one worker may run a job: it is claimed with a conditional UPDATE that stores a random
``lease_token``, and every checkpoint is written only if that token still matches (fencing). A
worker that lost its lease (it was slow, the sweeper gave the job to another) stops without
touching anything.
"""

import hashlib
import logging
import os
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.db import InterfaceError, OperationalError
from django.db.models import F, Q
from django.utils import timezone

from . import datasets
from .models import ExportJob

logger = logging.getLogger(__name__)

TRANSIENT_ERRORS = (
    OperationalError,
    InterfaceError,
    OSError,
    TimeoutError,
    ConnectionError,
)
FILE_NAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(part|csv|ndjson)$"
)
CONTENT_TYPES = {"csv": "text/csv; charset=utf-8", "ndjson": "application/x-ndjson"}


class ExportTooLarge(Exception):
    """The export would be bigger than EXPORT_MAX_BYTES; retrying cannot change that."""


class LostLease(Exception):
    """Another worker owns the job now (or it was cancelled); stop without writing anything."""


# ------------------------------------------------------------------------------- settings


def _setting(name, default):
    return getattr(settings, name, default)


def export_root() -> Path:
    root = Path(_setting("EXPORT_ROOT", Path(settings.BASE_DIR) / "export_files"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def chunk_rows() -> int:
    return max(1, int(_setting("EXPORT_CHUNK_ROWS", 1000)))


def max_attempts() -> int:
    return max(1, int(_setting("EXPORT_MAX_ATTEMPTS", 3)))


def lease_seconds() -> int:
    return int(_setting("EXPORT_LEASE_SECONDS", 300))


def max_bytes() -> int:
    return int(_setting("EXPORT_MAX_BYTES", 512 * 1024 * 1024))


def ttl() -> timedelta:
    return timedelta(hours=int(_setting("EXPORT_TTL_HOURS", 24)))


def part_path(job) -> Path:
    return export_root() / f"{job.id}.part"


def final_path(job) -> Path:
    return export_root() / f"{job.id}.{job.file_format}"


def remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Could not remove %s: %s", path, exc)


def backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(3600, 60 * 2 ** max(0, attempt - 1)))


# ---------------------------------------------------------------------------- job state


def claim(job_id) -> Optional[ExportJob]:
    """Take a queued job, or a running one whose worker stopped sending heartbeats."""
    now = timezone.now()
    token = uuid.uuid4()
    stale = now - timedelta(seconds=lease_seconds())
    taken = (
        ExportJob.objects.filter(pk=job_id)
        .filter(
            Q(status=ExportJob.QUEUED)
            | Q(status=ExportJob.RUNNING, heartbeat_at__lt=stale)
        )
        .update(
            status=ExportJob.RUNNING,
            lease_token=token,
            heartbeat_at=now,
            next_run_at=None,
            attempts=F("attempts") + 1,
        )
    )
    if not taken:
        return None
    ExportJob.objects.filter(pk=job_id, started_at__isnull=True).update(started_at=now)
    return ExportJob.objects.select_related("user").get(pk=job_id)


def _owned(job):
    return ExportJob.objects.filter(
        pk=job.pk, lease_token=job.lease_token, status=ExportJob.RUNNING
    )


def _checkpoint(job, last_pk, rows: int, nbytes: int) -> None:
    """Record that everything up to ``last_pk`` is in the file. Fenced by the lease token."""
    updated = _owned(job).update(
        checkpoint={"last_pk": last_pk, "rows": rows, "bytes": nbytes},
        rows_written=rows,
        bytes_written=nbytes,
        heartbeat_at=timezone.now(),
    )
    if not updated:
        raise LostLease()


def _still_mine(job) -> bool:
    """Refresh the cancel flag and confirm the lease before each chunk."""
    state = _owned(job).values_list("cancel_requested", flat=True).first()
    if state is None:
        raise LostLease()
    return not state  # False means "cancel requested"


def _finish(job, **fields) -> None:
    fields.setdefault("lease_token", None)
    fields.setdefault("finished_at", timezone.now())
    _owned(job).update(**fields)


def _cancel(job) -> str:
    remove_file(part_path(job))
    _finish(job, status=ExportJob.CANCELLED, error="")
    logger.info("Export %s cancelled", job.id)
    return ExportJob.CANCELLED


def _fail(job, message: str) -> str:
    remove_file(part_path(job))
    _finish(job, status=ExportJob.FAILED, error=message[:2000])
    logger.warning("Export %s failed: %s", job.id, message)
    return ExportJob.FAILED


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _complete(job, final: Path, rows: int) -> str:
    size = final.stat().st_size
    _finish(
        job,
        status=ExportJob.COMPLETED,
        file_name=final.name,
        sha256=_sha256(final),
        bytes_written=size,
        rows_written=rows,
        expires_at=timezone.now() + ttl(),
        error="",
    )
    logger.info("Export %s completed: %s rows, %s bytes", job.id, rows, size)
    return ExportJob.COMPLETED


# ------------------------------------------------------------------------------ the run


def run_job(job_id) -> Optional[str]:
    """
    Run (or resume) one export. Returns the job's status afterwards, or None when the job was not
    ours to run (already finished, or another worker holds it).
    """
    job = claim(job_id)
    if job is None:
        logger.info(
            "Export %s is not claimable (finished or held by another worker)", job_id
        )
        return None
    try:
        return _execute(job)
    except LostLease:
        logger.info("Export %s: lease lost, stopping", job.id)
        return None
    except (
        Exception
    ) as exc:  # BaseException (a killed worker) is deliberately not caught
        return _handle_error(job, exc)


def _handle_error(job, exc: Exception) -> Optional[str]:
    message = f"{exc.__class__.__name__}: {exc}"
    transient = isinstance(exc, TRANSIENT_ERRORS) and not isinstance(
        exc, FileNotFoundError
    )
    if transient and job.attempts < max_attempts():
        # Keep the file and the checkpoint: the next attempt resumes from them.
        updated = _owned(job).update(
            status=ExportJob.QUEUED,
            lease_token=None,
            next_run_at=timezone.now() + backoff(job.attempts),
            error=message[:2000],
        )
        logger.warning("Export %s will retry after: %s", job.id, message)
        return ExportJob.QUEUED if updated else None
    if isinstance(exc, (datasets.UnknownDataset, ExportTooLarge)):
        return _fail(job, str(exc.args[0]) if exc.args else message)
    return _fail(job, message)


def _prepare_part(job, part: Path):
    """
    Return ``(last_pk, rows, bytes)`` to continue from, with the part file cut back to exactly
    the checkpointed length. Anything past it was never confirmed and is discarded.
    """
    cp = job.checkpoint or {}
    last_pk, rows, nbytes = (
        cp.get("last_pk"),
        int(cp.get("rows", 0)),
        int(cp.get("bytes", 0)),
    )
    size = part.stat().st_size if part.exists() else 0
    if nbytes and size < nbytes:
        logger.warning(
            "Export %s: file is shorter than its checkpoint, starting over", job.id
        )
        last_pk, rows, nbytes = None, 0, 0
        size = 0
        remove_file(part)
    if size > nbytes:
        os.truncate(part, nbytes)
    return last_pk, rows, nbytes


def _execute(job) -> str:
    if job.attempts > max_attempts():
        return _fail(job, "Gave up after too many attempts")
    if job.cancel_requested:
        return _cancel(job)

    dataset = datasets.get_dataset(job.dataset)
    part, final = part_path(job), final_path(job)
    cp = job.checkpoint or {}

    # A previous worker renamed the finished file and died before saying so.
    if final.exists() and not part.exists():
        if final.stat().st_size == int(cp.get("bytes", -1)):
            return _complete(job, final, int(cp.get("rows", 0)))
        remove_file(final)
        job.checkpoint = {}

    last_pk, rows, nbytes = _prepare_part(job, part)
    columns = dataset.columns
    size_limit = max_bytes()

    with open(part, "ab" if nbytes else "wb") as fh:
        if nbytes == 0:
            header = datasets.encode_header(columns, job.file_format)
            if header:
                fh.write(header)
                fh.flush()
                os.fsync(fh.fileno())
            nbytes = len(header)
            _checkpoint(job, last_pk, rows, nbytes)

        while True:
            if not _still_mine(job):
                fh.close()
                return _cancel(job)
            chunk = datasets.fetch_chunk(dataset, job.user, last_pk, chunk_rows())
            if not chunk:
                break
            data = datasets.encode_rows(chunk, columns, job.file_format)
            if nbytes + len(data) > size_limit:
                raise ExportTooLarge(
                    f"The export is larger than the {size_limit} byte limit; narrow it down"
                )
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
            last_pk = chunk[-1][0]
            rows += len(chunk)
            nbytes += len(data)
            _checkpoint(job, last_pk, rows, nbytes)

    os.replace(part, final)
    return _complete(job, final, rows)
