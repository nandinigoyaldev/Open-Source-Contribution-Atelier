from datetime import datetime, timezone as dt_timezone
from django.db import transaction
from django.utils import timezone
from django_q.tasks import async_task

from apps.progress.models import (
    LessonProgress,
    LessonProgressSync,
    XPEvent,
    XPMultiplierEvent,
)
from apps.content.services.lesson_service import LessonService


class ProgressTrackingService:
    """
    Domain service for handling complex user progress business logic.
    Decoupled from HTTP request lifecycle and views.
    """

    @staticmethod
    def record_lesson_progress(
        user,
        lesson_slug: str,
        base_score: int = 100,
        completed: bool = True,
        idempotency_key: str = None,
        client_timestamp_ms: int = None,
    ) -> tuple[LessonProgress, bool, bool]:
        """
        Records or updates a user's progress for a specific lesson.
        Returns a tuple: (LessonProgress instance, created boolean, idempotency_hit boolean).
        """
        multiplier = XPMultiplierEvent.get_active_multiplier()
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
                skip_update = False
                if client_timestamp_ms:
                    client_dt = datetime.fromtimestamp(
                        client_timestamp_ms / 1000.0, tz=dt_timezone.utc
                    )
                    if progress.updated_at > client_dt:
                        skip_update = True

                if not skip_update and (
                    progress.base_score != base_score or progress.completed != completed
                ):
                    old_score = progress.score
                    progress.completed = completed
                    progress.base_score = base_score
                    progress.multiplier_applied = multiplier
                    progress.score = int(base_score * multiplier)
                    progress.organization = organization
                    progress.save(
                        update_fields=[
                            "completed",
                            "base_score",
                            "multiplier_applied",
                            "score",
                            "organization",
                            "updated_at",
                        ]
                    )

                    xp_delta = progress.score - old_score
                    if xp_delta != 0:
                        XPEvent.objects.create(
                            user=user,
                            source_type="lesson",
                            source_id=lesson.id,
                            base_points=base_score,
                            multiplier=multiplier,
                            xp_delta=xp_delta,
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

        return progress, created, False

    @staticmethod
    def bulk_sync_progress(user, lessons_data: list) -> list[int]:
        """
        Synchronizes multiple lessons' progress for a user.
        """
        multiplier = XPMultiplierEvent.get_active_multiplier()
        organization = getattr(user, "organization", None)
        synced_ids = []

        with transaction.atomic():
            for item in lessons_data:
                lesson_slug = item["lesson_slug"]
                base_score = item.get("score", 100)
                completed = item.get("completed", True)
                client_timestamp_ms = item.get("client_timestamp")

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
                    skip_update = False
                    if client_timestamp_ms:
                        client_dt = datetime.fromtimestamp(
                            client_timestamp_ms / 1000.0, tz=dt_timezone.utc
                        )
                        if progress.updated_at > client_dt:
                            skip_update = True

                    if not skip_update and (
                        progress.base_score != base_score
                        or progress.completed != completed
                    ):
                        old_score = progress.score
                        progress.completed = completed
                        progress.base_score = base_score
                        progress.multiplier_applied = multiplier
                        progress.score = int(base_score * multiplier)
                        progress.organization = organization
                        progress.save(
                            update_fields=[
                                "completed",
                                "base_score",
                                "multiplier_applied",
                                "score",
                                "organization",
                                "updated_at",
                            ]
                        )

                        xp_delta = progress.score - old_score
                        if xp_delta != 0:
                            XPEvent.objects.create(
                                user=user,
                                source_type="lesson",
                                source_id=lesson.id,
                                base_points=base_score,
                                multiplier=multiplier,
                                xp_delta=xp_delta,
                            )

                synced_ids.append(progress.id)

            transaction.on_commit(
                lambda: async_task(
                    "apps.progress.tasks.evaluate_user_badges_task", user.id
                )
            )

        return synced_ids
