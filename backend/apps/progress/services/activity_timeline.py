"""
Personal learning activity timeline.

A chronological, newest-first list of meaningful things a learner did: lessons completed, quiz
questions answered, certificates issued and badges earned. It is read-only and only ever returns
the requesting user's own activity.

Pagination is keyset based. The cursor is the position of the last item returned, so pages stay
stable when new activity arrives and cost the same however long the history is. Items are ordered by
``(occurred_at, type, id)`` descending, which is a total order, so items with the same timestamp are
never skipped or repeated.

Response shape (see ``ActivityTimelineView``)::

    {
      "results": [
        {
          "id": "lesson_completed:12",       # unique and stable: "<type>:<primary key>"
          "type": "lesson_completed",
          "occurred_at": "2026-10-27T09:30:00+00:00",
          "title": "Git basics",
          "description": "Score 80",          # short, optional ("" when there is nothing to add)
          "metadata": {"lesson_slug": "git-basics", "score": 80}
        }
      ],
      "next_cursor": "opaque-string-or-null",
      "has_more": true,
      "limit": 20,
      "types": ["lesson_completed", "quiz_attempt"]
    }

Known limitation: lesson progress has no separate completion time, so a completed lesson is dated by
its last update.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from django.db.models import Q, QuerySet

from ..models import Certificate, LessonProgress, QuizAttempt, UserBadge

LESSON_COMPLETED = "lesson_completed"
QUIZ_ATTEMPT = "quiz_attempt"
CERTIFICATE_ISSUED = "certificate_issued"
BADGE_EARNED = "badge_earned"

ACTIVITY_TYPES = (LESSON_COMPLETED, QUIZ_ATTEMPT, CERTIFICATE_ISSUED, BADGE_EARNED)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_TITLE_LENGTH = 140


class TimelineError(ValueError):
    """A request the timeline cannot serve (bad type, limit or cursor)."""


@dataclass(frozen=True)
class Cursor:
    occurred_at: datetime
    type: str
    pk: int

    def encode(self) -> str:
        raw = json.dumps(
            [self.occurred_at.isoformat(), self.type, self.pk], separators=(",", ":")
        )
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> "Cursor":
        try:
            padded = value + "=" * (-len(value) % 4)
            occurred, type_, pk = json.loads(base64.urlsafe_b64decode(padded.encode()))
            when = datetime.fromisoformat(occurred)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if (
                type_ not in ACTIVITY_TYPES
                or isinstance(pk, bool)
                or not isinstance(pk, int)
            ):
                raise ValueError("bad cursor fields")
            return cls(when, type_, pk)
        except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
            raise TimelineError("Invalid cursor.") from exc


def parse_types(raw: Optional[Iterable[str]]) -> tuple:
    """Turn the ``type`` query values (repeated or comma separated) into a validated tuple.

    An empty value means every type. An unknown type is an error rather than being ignored, so a
    typo in a filter never silently shows everything.
    """
    requested: list = []
    for chunk in raw or ():
        for part in str(chunk).split(","):
            part = part.strip()
            if part and part not in requested:
                requested.append(part)
    unknown = [t for t in requested if t not in ACTIVITY_TYPES]
    if unknown:
        raise TimelineError(
            "Unknown activity type: %s. Use one of: %s."
            % (", ".join(unknown), ", ".join(ACTIVITY_TYPES))
        )
    # Keep a stable order that does not depend on how the client wrote the filter.
    return tuple(t for t in ACTIVITY_TYPES if t in requested) or ACTIVITY_TYPES


def parse_limit(raw: Any) -> int:
    if raw in (None, ""):
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise TimelineError("limit must be a whole number.") from exc
    if value < 1:
        raise TimelineError("limit must be at least 1.")
    return min(value, MAX_LIMIT)


def _shorten(text: str, length: int = MAX_TITLE_LENGTH) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _before(qs: QuerySet, field: str, type_: str, cursor: Optional[Cursor]) -> QuerySet:
    """Keep only rows that sort strictly after ``cursor`` in newest-first order."""
    if cursor is None:
        return qs
    when = cursor.occurred_at
    if type_ == cursor.type:
        return qs.filter(
            Q(**{f"{field}__lt": when}) | Q(**{field: when, "pk__lt": cursor.pk})
        )
    if type_ < cursor.type:
        # Same timestamp, but this type sorts lower than the cursor's type.
        return qs.filter(**{f"{field}__lte": when})
    return qs.filter(**{f"{field}__lt": when})


def _lessons(user, cursor, limit):
    qs = LessonProgress.objects.filter(user=user, completed=True).select_related(
        "lesson"
    )
    qs = _before(qs, "updated_at", LESSON_COMPLETED, cursor)
    for row in qs.order_by("-updated_at", "-pk")[: limit + 1]:
        yield {
            "type": LESSON_COMPLETED,
            "pk": row.pk,
            "occurred_at": row.updated_at,
            "title": _shorten(row.lesson.title),
            "description": f"Score {row.score}" if row.score else "",
            "metadata": {"lesson_slug": row.lesson.slug, "score": row.score},
        }


def _quizzes(user, cursor, limit):
    qs = _before(
        QuizAttempt.objects.filter(user=user), "created_at", QUIZ_ATTEMPT, cursor
    )
    for row in qs.order_by("-created_at", "-pk")[: limit + 1]:
        yield {
            "type": QUIZ_ATTEMPT,
            "pk": row.pk,
            "occurred_at": row.created_at,
            "title": _shorten(row.question_text) or "Quiz question",
            "description": "Correct" if row.is_correct else "Incorrect",
            "metadata": {
                "question_id": row.question_id,
                "is_correct": row.is_correct,
                "time_taken_seconds": row.time_taken_seconds,
            },
        }


def _certificates(user, cursor, limit):
    qs = Certificate.objects.filter(user=user, is_active=True)
    qs = _before(qs, "issued_at", CERTIFICATE_ISSUED, cursor)
    for row in qs.order_by("-issued_at", "-pk")[: limit + 1]:
        yield {
            "type": CERTIFICATE_ISSUED,
            "pk": row.pk,
            "occurred_at": row.issued_at,
            "title": _shorten(row.course_name),
            "description": "Certificate issued",
            "metadata": {"verification_hash": str(row.verification_hash)},
        }


def _badges(user, cursor, limit):
    qs = UserBadge.objects.filter(user=user).select_related("badge")
    qs = _before(qs, "earned_at", BADGE_EARNED, cursor)
    for row in qs.order_by("-earned_at", "-pk")[: limit + 1]:
        yield {
            "type": BADGE_EARNED,
            "pk": row.pk,
            "occurred_at": row.earned_at,
            "title": _shorten(row.badge.name),
            "description": _shorten(row.badge.description, 200),
            "metadata": {"badge_slug": row.badge.slug, "category": row.badge.category},
        }


_SOURCES: dict = {
    LESSON_COMPLETED: _lessons,
    QUIZ_ATTEMPT: _quizzes,
    CERTIFICATE_ISSUED: _certificates,
    BADGE_EARNED: _badges,
}


def _sort_key(item: dict) -> tuple:
    return (item["occurred_at"], item["type"], item["pk"])


def _public(item: dict) -> dict:
    return {
        "id": f"{item['type']}:{item['pk']}",
        "type": item["type"],
        "occurred_at": item["occurred_at"].isoformat(),
        "title": item["title"],
        "description": item["description"],
        "metadata": item["metadata"],
    }


def get_activity_timeline(
    user,
    types: Optional[Iterable[str]] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: Optional[str] = None,
) -> dict:
    """One page of the user's activity, newest first. ``types`` must already be validated."""
    selected = tuple(types) if types else ACTIVITY_TYPES
    decoded = Cursor.decode(cursor) if cursor else None

    # Each source returns at most ``limit + 1`` rows after the cursor, so the merge is bounded by
    # the page size however much history there is.
    merged: list = []
    for type_ in selected:
        merged.extend(_SOURCES[type_](user, decoded, limit))
    merged.sort(key=_sort_key, reverse=True)

    page = merged[:limit]
    has_more = len(merged) > limit
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = Cursor(last["occurred_at"], last["type"], last["pk"]).encode()

    return {
        "results": [_public(item) for item in page],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "limit": limit,
        "types": list(selected),
    }
