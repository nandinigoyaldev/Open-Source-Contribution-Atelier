from django.db import transaction
from django.utils import timezone
from django_q.tasks import async_task

from apps.content.services.lesson_service import LessonService
from apps.progress.models import (
    DailyActivity,
    LessonProgress,
    LessonProgressSync,
    XPEvent,
    XPMultiplierEvent,
)
from apps.progress.services.progress_versioning import (
    APPLY,
    CONFLICT,
    ProgressVersionConflict,
    apply_write,
    conflict_payload,
    decide_write,
)


class ProgressTrackingService:
    """
    Domain service for handling complex user progress business logic.
    Decoupled from HTTP request lifecycle and views.
    """

    @staticmethod
    def _write_existing_row(
        progress,
        user,
        lesson,
        organization,
        base_score,
        completed,
        multiplier,
        expected_version,
    ) -> str:
        """Writes to a row that is already locked, returns the decide_write outcome."""
        decision = decide_write(
            progress, base_score, completed, multiplier, expected_version
        )
        if decision.outcome == APPLY:
            xp_delta = apply_write(progress, decision)
            progress.organization = organization
            progress.save(
                update_fields=[
                    "completed",
                    "base_score",
                    "multiplier_applied",
                    "score",
                    "organization",
                    "version",
                    "updated_at",
                ]
            )

            if xp_delta != 0:
                XPEvent.objects.create(
                    user=user,
                    source_type="lesson",
                    source_id=lesson.id,
                    base_points=decision.base_score,
                    multiplier=decision.multiplier,
                    xp_delta=xp_delta,
                )
        return decision.outcome

    @staticmethod
    def record_lesson_progress(
        user,
        lesson_slug: str,
        base_score: int = 100,
        completed: bool = True,
        idempotency_key: str = None,
        client_timestamp_ms: int = None,
        expected_version: int | None = None,
    ) -> tuple[LessonProgress, bool, bool]:
        """
        Records or updates a user's progress for a specific lesson.
        Returns a tuple: (LessonProgress instance, created boolean, idempotency_hit boolean).
        Raises ProgressVersionConflict if the write is refused, see decide_write().
        """
        from apps.progress.services.milestone_track_service import MilestoneTrackService

        season_mult = MilestoneTrackService.get_active_season_multiplier(user, "lesson")
        multiplier = XPMultiplierEvent.get_active_multiplier() * season_mult
        organization = getattr(user, "organization", None)

        lesson = LessonService.get_lesson_by_slug(lesson_slug, organization)

        with transaction.atomic():
            (
                progress,
                created,
            ) = LessonProgress.objects.select_for_update().get_or_create(
                user=user,
                lesson=lesson,
                defaults={
                    "organization": organization,
                    "completed": completed,
                    "base_score": base_score,
                    "multiplier_applied": multiplier,
                    "score": int(base_score * multiplier),
                },
            )

            if idempotency_key:
                sync_row = LessonProgressSync.objects.filter(
                    user=user,
                    lesson=lesson,
                    idempotency_key=idempotency_key,
                ).first()

                if sync_row is not None:
                    transaction.on_commit(
                        lambda: async_task(
                            "apps.progress.tasks.evaluate_user_badges_task", user.id
                        )
                    )
                    return progress, False, True

            outcome = APPLY
            if created:
                if progress.score != 0:
                    XPEvent.objects.create(
                        user=user,
                        source_type="lesson",
                        source_id=lesson.id,
                        base_points=base_score,
                        multiplier=multiplier,
                        xp_delta=progress.score,
                    )
            else:
                outcome = ProgressTrackingService._write_existing_row(
                    progress,
                    user,
                    lesson,
                    organization,
                    base_score,
                    completed,
                    multiplier,
                    expected_version,
                )
                if outcome == CONFLICT:
                    # No sync row on purpose: the key was not spent, so the same
                    # attempt can come back with a fresh version.
                    raise ProgressVersionConflict(
                        conflict_payload(progress, expected_version)
                    )

            if idempotency_key:
                LessonProgressSync.objects.create(
                    user=user,
                    lesson=lesson,
                    idempotency_key=idempotency_key,
                    completed=progress.completed,
                    base_score=progress.base_score,
                    multiplier_applied=progress.multiplier_applied,
                    score=progress.score,
                    client_timestamp_ms=client_timestamp_ms,
                    server_updated_at=timezone.now(),
                )

            transaction.on_commit(
                lambda: async_task(
                    "apps.progress.tasks.evaluate_user_badges_task", user.id
                )
            )

            if completed and outcome == APPLY:
                try:
                    local_date = user.user_profile.local_today
                except Exception:
                    local_date = timezone.now().date()
                DailyActivity.log_and_update_streak(
                    user=user,
                    date=local_date,
                    activity_type="lesson",
                )

        return progress, created, False

    @staticmethod
    def bulk_sync_progress(user, lessons_data: list) -> tuple[list[int], list[dict]]:
        """
        Synchronizes multiple lessons' progress for a user.
        Returns (ids of rows that match what was sent, one conflict per refused item).
        A refused item does not stop the others.
        """
        from apps.progress.services.milestone_track_service import MilestoneTrackService

        season_mult = MilestoneTrackService.get_active_season_multiplier(user, "lesson")
        multiplier = XPMultiplierEvent.get_active_multiplier() * season_mult
        organization = getattr(user, "organization", None)
        synced_ids = []
        conflicts = []

        with transaction.atomic():
            for item in lessons_data:
                lesson_slug = item["lesson_slug"]
                base_score = item.get("score", 100)
                completed = item.get("completed", True)
                expected_version = item.get("expected_version")

                lesson = LessonService.get_or_create_dynamic_lesson(lesson_slug)

                (
                    progress,
                    created,
                ) = LessonProgress.objects.select_for_update().get_or_create(
                    user=user,
                    lesson=lesson,
                    defaults={
                        "completed": completed,
                        "base_score": base_score,
                        "multiplier_applied": multiplier,
                        "score": int(base_score * multiplier),
                        "organization": organization,
                    },
                )

                if not created:
                    outcome = ProgressTrackingService._write_existing_row(
                        progress,
                        user,
                        lesson,
                        organization,
                        base_score,
                        completed,
                        multiplier,
                        expected_version,
                    )
                    if outcome == CONFLICT:
                        conflicts.append(conflict_payload(progress, expected_version))
                        continue

                synced_ids.append(progress.id)

            transaction.on_commit(
                lambda: async_task(
                    "apps.progress.tasks.evaluate_user_badges_task", user.id
                )
            )

        return synced_ids, conflicts
