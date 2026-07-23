import datetime
from django.db import transaction
from django_q.tasks import async_task
from apps.content.models import Lesson
from apps.progress.models import LessonProgress, XPMultiplierEvent


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
    Returns a list of created/updated LessonProgress IDs.
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

    success_ids = []

    with transaction.atomic():
        lesson_slugs = list(seen_slugs)
        existing_lessons = {
            lesson.slug: lesson
            for lesson in Lesson.objects.filter(slug__in=lesson_slugs)
        }

        # Validation: Invalid lesson IDs
        missing_slugs = [slug for slug in lesson_slugs if slug not in existing_lessons]

        if missing_slugs:
            # rollback transaction if anything fails validation
            raise InvalidLessonException(missing_slugs)

        existing_progress = {
            progress.lesson_id: progress
            for progress in LessonProgress.objects.filter(
                user=user, lesson__slug__in=lesson_slugs
            )
        }

        progress_to_create = []
        progress_to_update = []

        from apps.progress.services.milestone_track_service import MilestoneTrackService

        season_mult = MilestoneTrackService.get_active_season_multiplier(user, "lesson")
        multiplier = XPMultiplierEvent.get_active_multiplier() * season_mult

        xp_events_to_create = []

        for item in validated_data:
            lesson = existing_lessons[item["lesson_slug"]]
            completed = item.get("completed", True)
            base_score = item.get("score", 100)

            if lesson.id in existing_progress:
                prog = existing_progress[lesson.id]

                client_timestamp_ms = item.get("client_timestamp")
                skip_update = False
                if client_timestamp_ms:
                    client_dt = datetime.datetime.fromtimestamp(
                        client_timestamp_ms / 1000.0, tz=datetime.timezone.utc
                    )
                    if prog.updated_at > client_dt:
                        skip_update = True

                if not skip_update and (
                    prog.base_score != base_score or prog.completed != completed
                ):
                    old_score = prog.score
                    prog.completed = completed
                    prog.base_score = base_score
                    prog.multiplier_applied = multiplier
                    prog.score = int(base_score * multiplier)
                    progress_to_update.append(prog)

                    xp_delta = prog.score - old_score
                    if xp_delta != 0:
                        from apps.progress.models import XPEvent

                        xp_events_to_create.append(
                            XPEvent(
                                user=user,
                                source_type="lesson",
                                source_id=lesson.id,
                                base_points=base_score,
                                multiplier=multiplier,
                                xp_delta=xp_delta,
                            )
                        )
            else:
                prog_score = int(base_score * multiplier)
                progress_to_create.append(
                    LessonProgress(
                        user=user,
                        lesson=lesson,
                        completed=completed,
                        base_score=base_score,
                        multiplier_applied=multiplier,
                        score=prog_score,
                    )
                )
                if prog_score != 0:
                    from apps.progress.models import XPEvent

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
            success_ids.extend([p.id for p in created_progresses])

        if progress_to_update:
            LessonProgress.objects.bulk_update(
                progress_to_update,
                ["completed", "score", "base_score", "multiplier_applied"],
            )
            success_ids.extend([p.id for p in progress_to_update])

        if xp_events_to_create:
            from apps.progress.models import XPEvent

            XPEvent.objects.bulk_create(xp_events_to_create)

        async_task("apps.progress.tasks.evaluate_user_badges_task", user.id)

    return success_ids
