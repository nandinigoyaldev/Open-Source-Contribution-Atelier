from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone
from django_q.tasks import async_task

from apps.content.models import Lesson
from apps.progress.models import (
    DailyActivity,
    LessonProgress,
    XPEvent,
    XPMultiplierEvent,
)
from apps.progress.services.progress_versioning import (
    APPLY,
    CONFLICT,
    apply_write,
    conflict_payload,
    decide_write,
)


@dataclass
class BulkUpdateResult:
    updated_ids: list = field(default_factory=list)
    # One entry per refused item, the batch itself still commits
    conflicts: list = field(default_factory=list)
    # Current version by lesson slug for every item that was not refused
    versions: dict = field(default_factory=dict)


class DuplicateEntryException(Exception):
    def __init__(self, duplicates):
        self.duplicates = duplicates
        super().__init__(f"Duplicate entries found: {duplicates}")


class InvalidLessonException(Exception):
    def __init__(self, missing_slugs):
        self.missing_slugs = missing_slugs
        super().__init__(f"Invalid lesson IDs: {missing_slugs}")


def process_bulk_progress_updates(user, validated_data):
    """
    Processes a bulk batch of lesson progress updates.
    Returns a BulkUpdateResult. Items that fail the version check land in its
    conflicts list and leave their row alone.
    Raises DuplicateEntryException or InvalidLessonException on validation failure.
    """
    # Check for duplicate entries within the same request
    seen_slugs = set()
    duplicates = set()
    for item in validated_data:
        slug = item["lesson_slug"]
        if slug in seen_slugs:
            duplicates.add(slug)
        seen_slugs.add(slug)

    if duplicates:
        raise DuplicateEntryException(list(duplicates))

    try:
        return _write_batch(user, validated_data, list(seen_slugs))
    except IntegrityError:
        # Another request inserted one of these rows first. Go again, the row
        # exists now and gets the same version check as any other.
        return _write_batch(user, validated_data, list(seen_slugs))


def _write_batch(user, validated_data, lesson_slugs):
    result = BulkUpdateResult()

    with transaction.atomic():
        existing_lessons = {
            lesson.slug: lesson
            for lesson in Lesson.objects.filter(slug__in=lesson_slugs)
        }

        # Validation: Invalid lesson IDs
        missing_slugs = [slug for slug in lesson_slugs if slug not in existing_lessons]

        if missing_slugs:
            # rollback transaction if anything fails validation
            raise InvalidLessonException(missing_slugs)

        # Locked in a fixed order so two batches can't deadlock on each other
        existing_progress = {
            progress.lesson_id: progress
            for progress in LessonProgress.objects.select_for_update()
            .filter(user=user, lesson__in=list(existing_lessons.values()))
            .order_by("lesson_id")
        }

        progress_to_create = []
        progress_to_update = []

        from apps.progress.services.milestone_track_service import MilestoneTrackService

        season_mult = MilestoneTrackService.get_active_season_multiplier(user, "lesson")
        multiplier = XPMultiplierEvent.get_active_multiplier() * season_mult
        organization = getattr(user, "organization", None)

        xp_events_to_create = []
        has_new_completion = False

        for item in validated_data:
            lesson = existing_lessons[item["lesson_slug"]]
            completed = item.get("completed", True)
            base_score = item.get("score", 100)
            expected_version = item.get("expected_version")

            if lesson.id in existing_progress:
                prog = existing_progress[lesson.id]
                prog.lesson = lesson

                decision = decide_write(
                    prog, base_score, completed, multiplier, expected_version
                )
                if decision.outcome == CONFLICT:
                    result.conflicts.append(conflict_payload(prog, expected_version))
                    continue

                if decision.outcome == APPLY:
                    if decision.completed and not prog.completed:
                        has_new_completion = True
                    xp_delta = apply_write(prog, decision)
                    prog.organization = organization
                    progress_to_update.append(prog)

                    if xp_delta != 0:
                        xp_events_to_create.append(
                            XPEvent(
                                user=user,
                                source_type="lesson",
                                source_id=lesson.id,
                                base_points=decision.base_score,
                                multiplier=decision.multiplier,
                                xp_delta=xp_delta,
                            )
                        )
                result.versions[lesson.slug] = prog.version
            else:
                if completed:
                    has_new_completion = True
                prog_score = int(base_score * multiplier)
                progress_to_create.append(
                    LessonProgress(
                        user=user,
                        lesson=lesson,
                        organization=organization,
                        completed=completed,
                        base_score=base_score,
                        multiplier_applied=multiplier,
                        score=prog_score,
                    )
                )
                if prog_score != 0:
                    xp_events_to_create.append(
                        XPEvent(
                            user=user,
                            source_type="lesson",
                            source_id=lesson.id,
                            base_points=base_score,
                            multiplier=multiplier,
                            xp_delta=prog_score,
                        )
                    )

        if progress_to_create:
            created_progresses = LessonProgress.objects.bulk_create(progress_to_create)
            result.updated_ids.extend([p.id for p in created_progresses])
            for created in created_progresses:
                result.versions[created.lesson.slug] = created.version

        if progress_to_update:
            LessonProgress.objects.bulk_update(
                progress_to_update,
                [
                    "completed",
                    "score",
                    "base_score",
                    "multiplier_applied",
                    "organization",
                    "version",
                    "updated_at",
                ],
            )
            result.updated_ids.extend([p.id for p in progress_to_update])

        if xp_events_to_create:
            XPEvent.objects.bulk_create(xp_events_to_create)

        if has_new_completion:
            DailyActivity.log_and_update_streak(
                user=user, date=timezone.now(), activity_type="lesson"
            )

        async_task("apps.progress.tasks.evaluate_user_badges_task", user.id)

    return result
