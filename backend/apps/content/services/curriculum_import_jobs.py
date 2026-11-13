# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
"""
State machine for bulk curriculum imports.

    validating -> previewed -> publishing -> published
         \\______________\\___________\\______> failed

* ``create_import`` stores the uploaded archive and a ``CurriculumImport`` row.
* ``run_validation`` walks the lessons in chunks. After every chunk it saves the
  cursor and the partial report on the row, so a crashed worker re-enters at the
  first unfinished chunk. Nothing in the curriculum is touched.
* ``run_publish`` applies the archive inside one database transaction. If any
  step raises, the transaction rolls back and the existing curriculum is left
  exactly as it was; the row then moves to ``failed`` with the error recorded.

The Celery tasks in ``apps.content.tasks`` and the ``import_curriculum``
management command are thin wrappers around these functions.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from apps.content.models import CurriculumImport, Lesson

from . import curriculum_import as ci

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 25
MAX_REPORTED_PROBLEMS = 500


class ImportStateError(Exception):
    """The requested transition is not allowed from the current status."""


def chunk_size() -> int:
    return max(
        1, int(getattr(settings, "CURRICULUM_IMPORT_CHUNK_SIZE", DEFAULT_CHUNK_SIZE))
    )


def max_archive_bytes() -> int:
    return int(
        getattr(settings, "CURRICULUM_IMPORT_MAX_ARCHIVE_BYTES", 50 * 1024 * 1024)
    )


# ---------------------------------------------------------------------------
# Creating an import
# ---------------------------------------------------------------------------


def create_import(data: bytes, name: str = "", user=None) -> CurriculumImport:
    """Store ``data`` as a new import in the ``validating`` state."""
    if len(data) > max_archive_bytes():
        raise ci.ArchiveError(
            f"archive is {len(data)} bytes (limit {max_archive_bytes()})"
        )
    imp = CurriculumImport(
        original_name=(name or "")[:255],
        sha256=hashlib.sha256(data).hexdigest(),
        created_by=user if getattr(user, "pk", None) else None,
    )
    imp.archive.save(f"import-{imp.sha256[:12]}.zip", ContentFile(data), save=False)
    imp.save()
    return imp


def _sha256_of(imp: CurriculumImport) -> str:
    digest = hashlib.sha256()
    with imp.archive.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Lesson field mapping (shared by preview and publish)
# ---------------------------------------------------------------------------


def lesson_fields(entry: ci.LessonEntry, text: str) -> Dict[str, Any]:
    return {
        "title": entry.title,
        "summary": entry.summary or entry.title,
        "content": ci.strip_front_matter(text),
        "difficulty": entry.difficulty,
        "category": entry.module_title or "general",
        "estimated_minutes": entry.estimated_minutes,
        "order": (entry.index + 1) * 10,
    }


def _classify(
    lesson: Optional[Lesson], fields: Dict[str, Any], prereqs: List[str]
) -> str:
    if lesson is None:
        return "create"
    same = all(getattr(lesson, key) == value for key, value in fields.items())
    if same:
        current = set(lesson.prerequisites.values_list("slug", flat=True))
        same = current == set(prereqs)
    return "unchanged" if same else "update"


# ---------------------------------------------------------------------------
# Validation (resumable)
# ---------------------------------------------------------------------------


def _fail(imp: CurriculumImport, message: str) -> CurriculumImport:
    imp.status = CurriculumImport.FAILED
    imp.error = message
    imp.save(update_fields=["status", "error", "report", "updated_at"])
    return imp


def _new_report(result: ci.ManifestResult) -> Dict[str, Any]:
    quizzes = sum(entry.quiz_count for entry in result.lessons)
    return {
        "counts": {
            "modules": len(result.manifest.get("modules") or []),
            "lessons": len(result.lessons),
            "quizzes": quizzes,
        },
        "problems": list(result.problems),
        "plan": {"create": [], "update": [], "unchanged": []},
    }


def _add_problems(report: Dict[str, Any], found: List[ci.Problem]) -> None:
    report["problem_count"] = report.get(
        "problem_count", len(report["problems"])
    ) + len(found)
    room = MAX_REPORTED_PROBLEMS - len(report["problems"])
    if room > 0:
        report["problems"].extend(found[:room])
    report["problems_truncated"] = report["problem_count"] > len(report["problems"])


def run_validation(import_id: int) -> CurriculumImport:
    """Validate the archive, resuming from ``cursor``. Safe to call repeatedly."""
    imp = CurriculumImport.objects.get(pk=import_id)
    if imp.status != CurriculumImport.VALIDATING:
        return imp
    try:
        zf = ci.open_archive(imp.archive.open("rb"))
        result = ci.check_manifest(zf)
    except ci.ArchiveError as exc:
        imp.report = {
            "problems": [ci.problem("bad_archive", imp.original_name, str(exc))]
        }
        return _fail(imp, str(exc))

    with zf:
        slugs = [entry.slug for entry in result.lessons if entry.slug]
        if imp.cursor == 0 or "plan" not in imp.report:
            imp.cursor = 0
            imp.report = _new_report(result)
            imp.report["problem_count"] = len(result.problems)
            imp.report["problems_truncated"] = False
            if len(result.problems) > MAX_REPORTED_PROBLEMS:
                imp.report["problems"] = list(result.problems[:MAX_REPORTED_PROBLEMS])
                imp.report["problems_truncated"] = True
        imp.total_lessons = len(result.lessons)

        entries = result.lessons
        for start in range(imp.cursor, len(entries), chunk_size()):
            chunk = entries[start : start + chunk_size()]
            existing = {
                lesson.slug: lesson
                for lesson in Lesson.objects.filter(
                    slug__in=[e.slug for e in chunk if e.slug]
                ).prefetch_related("prerequisites")
            }
            for entry in chunk:
                found = ci.validate_lesson_file(zf, entry, slugs)
                _add_problems(imp.report, found)
                if not found and entry.slug and entry.file_path:
                    try:
                        fields = lesson_fields(entry, ci.decode_lesson(zf, entry))
                    except (ci.ArchiveError, UnicodeDecodeError, KeyError):
                        continue
                    action = _classify(
                        existing.get(entry.slug), fields, list(entry.prerequisites)
                    )
                    imp.report["plan"][action].append(entry.slug)
            imp.cursor = start + len(chunk)
            imp.save(update_fields=["cursor", "report", "total_lessons", "updated_at"])

    if imp.report.get("problem_count"):
        return _fail(imp, f"validation found {imp.report['problem_count']} problem(s)")
    imp.status = CurriculumImport.PREVIEWED
    imp.error = ""
    imp.save(
        update_fields=[
            "status",
            "error",
            "cursor",
            "report",
            "total_lessons",
            "updated_at",
        ]
    )
    return imp


# ---------------------------------------------------------------------------
# Publishing (one transaction)
# ---------------------------------------------------------------------------


def _apply(imp: CurriculumImport, zf, entries: List[ci.LessonEntry]) -> Dict[str, int]:
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    slug_to_lesson: Dict[str, Lesson] = {}
    for start in range(0, len(entries), chunk_size()):
        chunk = entries[start : start + chunk_size()]
        existing = {
            lesson.slug: lesson
            for lesson in Lesson.objects.filter(
                slug__in=[e.slug for e in chunk]
            ).prefetch_related("prerequisites")
        }
        for entry in chunk:
            fields = lesson_fields(entry, ci.decode_lesson(zf, entry))
            lesson = existing.get(entry.slug)
            action = _classify(lesson, fields, list(entry.prerequisites))
            if action == "create":
                lesson = Lesson(slug=entry.slug, **fields)
                lesson.save()
                counts["created"] += 1
            elif action == "update":
                assert lesson is not None
                for key, value in fields.items():
                    setattr(lesson, key, value)
                lesson.save()
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
            assert lesson is not None
            slug_to_lesson[entry.slug] = lesson

    # Prerequisites last, once every lesson of the archive exists.
    for entry in entries:
        lesson = slug_to_lesson[entry.slug]
        wanted = {slug_to_lesson[s].pk for s in entry.prerequisites}
        current = set(lesson.prerequisites.values_list("pk", flat=True))
        if wanted != current:
            lesson.prerequisites.set(wanted)
    return counts


def claim_for_publish(import_id: int) -> CurriculumImport:
    """Move ``previewed`` (or an interrupted ``publishing``) to ``publishing``."""
    claimed = CurriculumImport.objects.filter(
        pk=import_id,
        status__in=[CurriculumImport.PREVIEWED, CurriculumImport.PUBLISHING],
    ).update(status=CurriculumImport.PUBLISHING)
    imp = CurriculumImport.objects.get(pk=import_id)
    if not claimed:
        raise ImportStateError(
            f"import #{import_id} is {imp.status}; only a previewed import can be published"
        )
    return imp


def run_publish(import_id: int) -> CurriculumImport:
    """Publish a previewed import atomically. Re-running a published one is a no-op."""
    imp = CurriculumImport.objects.get(pk=import_id)
    if imp.status == CurriculumImport.PUBLISHED:
        return imp
    imp = claim_for_publish(import_id)
    try:
        if _sha256_of(imp) != imp.sha256:
            raise ci.ArchiveError("stored archive no longer matches its checksum")
        with ci.open_archive(imp.archive.open("rb")) as zf:
            result = ci.check_manifest(zf)
            if result.problems:
                raise ci.ArchiveError(
                    "archive no longer validates; run validation again"
                )
            with transaction.atomic():
                counts = _apply(imp, zf, result.lessons)
    except Exception as exc:  # noqa: BLE001 - every failure must leave a record
        logger.exception("curriculum import %s failed to publish", import_id)
        imp.report = {**imp.report, "publish_error": f"{type(exc).__name__}: {exc}"}
        return _fail(imp, f"publish failed and was rolled back: {exc}")

    imp.report = {**imp.report, "published": counts}
    imp.status = CurriculumImport.PUBLISHED
    imp.error = ""
    imp.save(update_fields=["status", "error", "report", "updated_at"])
    return imp
