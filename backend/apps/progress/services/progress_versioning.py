"""
The one rule for writing to a LessonProgress row.

Every write path (single write, bulk sync, bulk update, buffered flush) locks the
row and then asks decide_write() what to do, so none of them can quietly fall back
to last write wins.
"""

import logging
from dataclasses import dataclass
from typing import Any

from django.utils import timezone
from rest_framework.serializers import IntegerField

from apps.progress.serializers import LessonProgressSerializer

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter

    PROGRESS_WRITE_CONFLICTS = Counter(
        "progress_write_conflicts_total",
        "Lesson progress writes refused because they were behind the stored row",
        ["versioned"],
    )
except ImportError:
    PROGRESS_WRITE_CONFLICTS = None

APPLY = "apply"
NOOP = "noop"
CONFLICT = "conflict"

VERSION_CONFLICT_CODE = "progress_version_conflict"


@dataclass(frozen=True)
class WriteDecision:
    outcome: str
    completed: bool = False
    base_score: int = 0
    multiplier: float = 1.0
    score: int = 0


class ProgressVersionConflict(Exception):
    """A single write was refused. payload is the 409 body."""

    def __init__(self, payload: dict):
        self.payload = payload
        super().__init__(payload["detail"])


def parse_expected_version(value: Any) -> int | None:
    """Reads expected_version from a raw request body. Bad values raise a 400."""
    if value is None:
        return None
    field: Any = IntegerField(min_value=0)
    return field.run_validation(value)


def decide_write(
    progress,
    base_score: int,
    completed: bool,
    multiplier: float,
    expected_version: int | None = None,
) -> WriteDecision:
    """
    Decides what a write does to a row that is already locked.

    With expected_version this is compare and swap: a match is applied as sent
    (that client saw the latest state, so it may even lower the score), a mismatch
    is a conflict.

    Without it the client has not shown what it saw, so it can only move the lesson
    forward: completed never goes back to false and score never drops. Whatever
    moves forward is kept, a write with nothing new is a conflict.

    Sending what the row already holds is never a conflict, there is nothing to lose.
    """
    if progress.base_score == base_score and progress.completed == completed:
        return WriteDecision(NOOP)

    score = int(base_score * multiplier)

    if expected_version is not None:
        if expected_version != progress.version:
            return WriteDecision(CONFLICT)
        return WriteDecision(APPLY, completed, base_score, multiplier, score)

    gains_completion = completed and not progress.completed
    gains_score = score > progress.score
    if not gains_completion and not gains_score:
        return WriteDecision(CONFLICT)
    if gains_score:
        return WriteDecision(
            APPLY, progress.completed or completed, base_score, multiplier, score
        )
    return WriteDecision(
        APPLY, True, progress.base_score, progress.multiplier_applied, progress.score
    )


def apply_write(progress, decision: WriteDecision) -> int:
    """Puts an APPLY decision on the row and returns the XP delta. Caller saves."""
    xp_delta = decision.score - progress.score
    progress.completed = decision.completed
    progress.base_score = decision.base_score
    progress.multiplier_applied = decision.multiplier
    progress.score = decision.score
    progress.version += 1
    # bulk_update skips auto_now, so this can't be left to the field
    progress.updated_at = timezone.now()
    return xp_delta


def conflict_payload(progress, expected_version: int | None) -> dict:
    """
    Records a refused write and builds what the client gets back: the row as it is
    now (so it can show it and retry with this version) plus why it was refused.
    """
    logger.info(
        "Progress write refused: user=%s lesson=%s expected_version=%s version=%s",
        progress.user_id,
        progress.lesson_id,
        expected_version,
        progress.version,
    )
    if PROGRESS_WRITE_CONFLICTS is not None:
        PROGRESS_WRITE_CONFLICTS.labels(
            versioned=str(expected_version is not None).lower()
        ).inc()
    current: Any = LessonProgressSerializer(progress).data
    return {
        **current,
        "code": VERSION_CONFLICT_CODE,
        "detail": "This lesson's progress changed since this client last read it.",
        "expected_version": expected_version,
    }
