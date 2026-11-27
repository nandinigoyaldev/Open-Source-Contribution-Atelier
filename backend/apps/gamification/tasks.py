from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Quest, UserQuest

DEFAULT_BATCH_SIZE = 500


@shared_task
def assign_daily_quests(batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """Assign active daily and weekly quests to active users in bounded batches."""
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    week_start = today - timedelta(days=7)
    week_end = today + timedelta(days=7)

    daily_quest_ids = list(
        Quest.objects.filter(is_active=True, frequency="daily").values_list(
            "id", flat=True
        )
    )
    weekly_quest_ids = list(
        Quest.objects.filter(is_active=True, frequency="weekly").values_list(
            "id", flat=True
        )
    )
    if not daily_quest_ids and not weekly_quest_ids:
        return 0

    User = get_user_model()
    last_id = 0
    created_total = 0

    while True:
        user_ids = list(
            User.objects.filter(is_active=True, id__gt=last_id)
            .order_by("id")
            .values_list("id", flat=True)[:batch_size]
        )
        if not user_ids:
            break
        last_id = user_ids[-1]

        to_create: list[UserQuest] = []

        if daily_quest_ids:
            existing_daily = set(
                UserQuest.objects.filter(
                    user_id__in=user_ids,
                    quest_id__in=daily_quest_ids,
                    assigned_at__gte=today,
                    assigned_at__lt=tomorrow,
                ).values_list("user_id", "quest_id")
            )
            for user_id in user_ids:
                for quest_id in daily_quest_ids:
                    if (user_id, quest_id) not in existing_daily:
                        to_create.append(
                            UserQuest(
                                user_id=user_id,
                                quest_id=quest_id,
                                expires_at=tomorrow,
                            )
                        )

        if weekly_quest_ids:
            existing_weekly = set(
                UserQuest.objects.filter(
                    user_id__in=user_ids,
                    quest_id__in=weekly_quest_ids,
                    assigned_at__gte=week_start,
                ).values_list("user_id", "quest_id")
            )
            for user_id in user_ids:
                for quest_id in weekly_quest_ids:
                    if (user_id, quest_id) not in existing_weekly:
                        to_create.append(
                            UserQuest(
                                user_id=user_id,
                                quest_id=quest_id,
                                expires_at=week_end,
                            )
                        )

        if to_create:
            created = UserQuest.objects.bulk_create(to_create, ignore_conflicts=True)
            created_total += len(created)

    return created_total


@shared_task
def expire_old_quests(batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """Delete expired uncompleted user quests in bounded primary-key batches."""
    now = timezone.now()
    total_deleted = 0

    while True:
        batch_ids = list(
            UserQuest.objects.filter(expires_at__lt=now, completed=False)
            .order_by("id")
            .values_list("id", flat=True)[:batch_size]
        )
        if not batch_ids:
            break
        deleted, _ = UserQuest.objects.filter(id__in=batch_ids).delete()
        total_deleted += deleted

    return total_deleted
