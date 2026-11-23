"""Versioned lesson publishing: draft -> review -> published -> archived.

The Lesson row is what learners read and what progress rows point at. A
LessonVersion is a numbered snapshot of its title, summary and content.
Publishing copies a reviewed revision into the same Lesson row, so progress,
bookmarks and notes keep their foreign key; nothing here creates or deletes a
Lesson. Rollback never revives an old revision: it writes a new published one
that records which revision it restored.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.content.models import Lesson, LessonVersion

# Typed loosely because Pyright cannot follow atomic() without django-stubs.
atomic: Any = transaction.atomic

_author: ContextVar[Any] = ContextVar("lesson_revision_author", default=None)
_publishing: ContextVar[bool] = ContextVar("lesson_revision_publishing", default=False)


class RevisionError(Exception):
    """The revision cannot make the requested change."""


@contextmanager
def revision_author(user):
    """Credit revisions written by a direct Lesson save inside this block to ``user``."""
    token = _author.set(user if getattr(user, "is_authenticated", False) else None)
    try:
        yield
    finally:
        _author.reset(token)


def current_author():
    return _author.get()


def is_publishing() -> bool:
    """True while a revision is being copied into its Lesson row."""
    return _publishing.get()


def live_revision(lesson: Lesson) -> Optional[LessonVersion]:
    return (
        LessonVersion.objects.filter(lesson=lesson, status=LessonVersion.PUBLISHED)
        .order_by("-number")
        .first()
    )


def _lock(lesson: Lesson) -> Lesson:
    # Serialises revision numbering and publishing per lesson.
    return Lesson.objects.select_for_update().get(pk=lesson.pk)


def _matches(revision: LessonVersion, lesson: Lesson) -> bool:
    return (
        (revision.title or lesson.title) == lesson.title
        and revision.summary == lesson.summary
        and revision.content == lesson.content
    )


def _archive_live(lesson: Lesson) -> None:
    for revision in LessonVersion.objects.filter(
        lesson=lesson, status=LessonVersion.PUBLISHED
    ):
        revision.status = LessonVersion.ARCHIVED
        revision.save(update_fields=["status"])


def _apply_to_lesson(lesson: Lesson, revision: LessonVersion) -> None:
    lesson.title = revision.title or lesson.title
    lesson.summary = revision.summary or lesson.summary
    lesson.content = revision.content
    token = _publishing.set(True)
    try:
        lesson.save(update_fields=["title", "summary", "content"])
    finally:
        _publishing.reset(token)


def _save(revision: LessonVersion, fields) -> None:
    try:
        revision.save(update_fields=fields)
    except ValidationError as exc:
        raise RevisionError(" ".join(str(m) for m in exc.messages)) from exc


def create_draft(
    lesson: Lesson, *, author, content: str, title="", summary="", note=""
) -> LessonVersion:
    with atomic():
        _lock(lesson)
        return LessonVersion.objects.create(
            lesson=lesson,
            status=LessonVersion.DRAFT,
            author=author,
            title=title or lesson.title,
            summary=summary or lesson.summary,
            content=content,
            note=note,
        )


def submit_for_review(revision) -> LessonVersion:
    if revision.status != LessonVersion.DRAFT:
        raise RevisionError("Only drafts can be sent for review.")
    revision.status = LessonVersion.REVIEW
    _save(revision, ["status"])
    return revision


def archive(revision) -> LessonVersion:
    if revision.status not in (LessonVersion.DRAFT, LessonVersion.REVIEW):
        raise RevisionError(
            "Only drafts and revisions in review can be archived. Publish or roll "
            "back to replace the published revision."
        )
    revision.status = LessonVersion.ARCHIVED
    _save(revision, ["status"])
    return revision


def publish(revision, actor) -> LessonVersion:
    if revision.status != LessonVersion.REVIEW:
        raise RevisionError("Only revisions in review can be published.")
    with atomic():
        lesson = _lock(revision.lesson)
        _archive_live(lesson)
        revision.status = LessonVersion.PUBLISHED
        revision.published_at = timezone.now()
        revision.published_by = actor
        _save(revision, ["status", "published_at", "published_by"])
        _apply_to_lesson(lesson, revision)
    return revision


def rollback(
    lesson: Lesson, target: LessonVersion, actor, note: str = ""
) -> LessonVersion:
    """Publish a new revision with ``target``'s snapshot; ``target`` is not changed."""
    if target.lesson_id != lesson.pk:
        raise RevisionError("That revision belongs to another lesson.")
    if target.published_at is None:
        raise RevisionError("Only a revision that was published can be restored.")
    with atomic():
        lesson = _lock(lesson)
        live = live_revision(lesson)
        if live is not None and live.pk == target.pk:
            raise RevisionError(f"v{target.number} is already the published revision.")
        _archive_live(lesson)
        now = timezone.now()
        restored = LessonVersion.objects.create(
            lesson=lesson,
            status=LessonVersion.PUBLISHED,
            author=actor,
            title=target.title or lesson.title,
            summary=target.summary or lesson.summary,
            content=target.content,
            note=note or f"Rollback to v{target.number}",
            restored_from=target,
            published_at=now,
            published_by=actor,
        )
        _apply_to_lesson(lesson, restored)
    return restored


def record_live_edit(lesson: Lesson, author=None) -> Optional[LessonVersion]:
    """
    Store a direct Lesson save as its published revision.

    A direct save is already live for learners, so the snapshot goes straight
    to published and the previous published revision is archived. Saves that
    do not touch title, summary or content add nothing.
    """
    with atomic():
        lesson = Lesson.objects.select_for_update().filter(pk=lesson.pk).first()
        if lesson is None:  # deleted before the save was committed
            return None
        live = live_revision(lesson)
        if live is not None and _matches(live, lesson):
            return None
        _archive_live(lesson)
        return LessonVersion.objects.create(
            lesson=lesson,
            status=LessonVersion.PUBLISHED,
            author=author,
            title=lesson.title,
            summary=lesson.summary,
            content=lesson.content,
            published_at=timezone.now(),
            published_by=author,
        )
