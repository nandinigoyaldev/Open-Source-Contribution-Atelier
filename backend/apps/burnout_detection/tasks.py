"""
Celery tasks for burnout detection.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.burnout_detection.models import (
    BurnoutActivityDay,
    BurnoutSignal,
    ContributorActivity,
    Intervention,
)
from apps.burnout_detection.services.burnout_detector import BurnoutDetector

logger = logging.getLogger(__name__)

HIGH_ACTIVITY_HOURS = 8.0
HIGH_ACTIVITY_STREAK_DAYS = 5
ROLLING_WINDOW_DAYS = 7
DEFAULT_BATCH_SIZE = 500


def _is_high_activity_day(day, weekend_learning_enabled: bool) -> bool:
    """Return whether a day should count toward the sustained high-activity streak."""
    if day.date.weekday() >= 5 and not weekend_learning_enabled:
        return False
    return day.active_hours >= HIGH_ACTIVITY_HOURS


def _has_sustained_high_activity(days, weekend_learning_enabled: bool) -> bool:
    """Require five consecutive high-activity days before flagging burnout risk."""
    streak = 0
    previous_date = None

    for day in sorted(days, key=lambda item: item.date):
        if not _is_high_activity_day(day, weekend_learning_enabled):
            streak = 0
            previous_date = day.date
            continue

        if previous_date is not None and day.date != previous_date + timedelta(days=1):
            streak = 0

        streak += 1
        if streak >= HIGH_ACTIVITY_STREAK_DAYS:
            return True
        previous_date = day.date

    return False


@shared_task
def detect_user_burnout_risk(batch_size: int = DEFAULT_BATCH_SIZE):
    """Flag users with five consecutive high-duration study days in a 7-day window."""
    User = get_user_model()
    today = timezone.localdate()
    window_start = today - timedelta(days=ROLLING_WINDOW_DAYS - 1)
    flagged_count = 0
    last_id = 0

    while True:
        users = list(
            User.objects.select_related("user_profile")
            .filter(id__gt=last_id)
            .order_by("id")[:batch_size]
        )
        if not users:
            break
        last_id = users[-1].id
        user_ids = [user.id for user in users]

        days_by_user: dict[int, list[BurnoutActivityDay]] = defaultdict(list)
        for day in BurnoutActivityDay.objects.filter(
            user_id__in=user_ids, date__gte=window_start, date__lte=today
        ):
            days_by_user[day.user_id].append(day)

        flagged_users = []
        for user in users:
            profile = getattr(user, "user_profile", None)
            weekend_learning_enabled = bool(
                profile and getattr(profile, "weekend_learning_enabled", False)
            )
            if _has_sustained_high_activity(
                days_by_user.get(user.id, []), weekend_learning_enabled
            ):
                flagged_users.append(user)

        if not flagged_users:
            continue

        existing_user_ids = set(
            BurnoutSignal.objects.filter(
                user_id__in=[u.id for u in flagged_users],
                signal_type="irregular_pattern",
                is_resolved=False,
            ).values_list("user_id", flat=True)
        )
        new_users = [u for u in flagged_users if u.id not in existing_user_ids]
        if not new_users:
            continue

        description = (
            "Sustained high-duration learning activity detected for "
            f"at least {HIGH_ACTIVITY_STREAK_DAYS} consecutive days."
        )
        BurnoutSignal.objects.bulk_create(
            [
                BurnoutSignal(
                    user=user,
                    signal_type="irregular_pattern",
                    is_resolved=False,
                    severity="severe",
                    description=description,
                )
                for user in new_users
            ]
        )
        for user in new_users:
            trigger_intervention.delay(user.id)
        flagged_count += len(new_users)

    logger.info("Detected %s sustained high-activity burnout cases", flagged_count)
    return {"flagged": flagged_count}


@shared_task
def detect_burnout(batch_size: int = DEFAULT_BATCH_SIZE):
    """
    Detect burnout in all contributors using keyset-paginated batches.
    """
    logger.info("Starting burnout detection")

    detector = BurnoutDetector()
    detected_count = 0
    critical_count = 0
    last_id = None

    while True:
        qs = ContributorActivity.objects.select_related("user").order_by("id")
        if last_id is not None:
            qs = qs.filter(id__gt=last_id)
        activities = list(qs[:batch_size])
        if not activities:
            break
        last_id = activities[-1].id

        pending_signals: list[tuple[int, dict]] = []
        intervene_user_ids: set[int] = set()

        for activity in activities:
            try:
                result = detector.detect_burnout(activity)
                if not result["needs_intervention"]:
                    continue

                detected_count += 1
                if result["risk_level"] == "critical":
                    critical_count += 1

                for signal_data in result["signals"]:
                    pending_signals.append((activity.user_id, signal_data))
                intervene_user_ids.add(activity.user_id)
            except (
                Exception
            ) as e:  # noqa: BLE001 - isolate per-activity detection failures
                logger.error(
                    "Error detecting burnout for %s: %s",
                    activity.user.username,
                    e,
                )

        if not pending_signals:
            continue

        existing_pairs = set(
            BurnoutSignal.objects.filter(
                user_id__in=intervene_user_ids,
                is_resolved=False,
            ).values_list("user_id", "signal_type")
        )

        signals_to_create = []
        newly_signaled_users: set[int] = set()
        for user_id, signal_data in pending_signals:
            pair = (user_id, signal_data["type"])
            if pair in existing_pairs:
                continue
            existing_pairs.add(pair)
            signals_to_create.append(
                BurnoutSignal(
                    user_id=user_id,
                    signal_type=signal_data["type"],
                    severity=signal_data["severity"],
                    description=signal_data["description"],
                )
            )
            newly_signaled_users.add(user_id)

        if signals_to_create:
            BurnoutSignal.objects.bulk_create(signals_to_create)
            for user_id in sorted(newly_signaled_users):
                trigger_intervention.delay(user_id)

    logger.info(
        "Detected %s burnout cases (%s critical)", detected_count, critical_count
    )
    return {"detected": detected_count, "critical": critical_count}


@shared_task
def trigger_intervention(user_id: int):
    """
    Trigger intervention for a user.
    """
    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)
        signal = BurnoutSignal.objects.filter(user=user, is_resolved=False).first()

        if not signal:
            return

        intervention_type = "encouragement"
        message = (
            "We've noticed you've been working hard. Take a break and recharge! 💪"
        )

        if signal.signal_type == "declining_activity":
            intervention_type = "encouragement"
            message = (
                "Your contributions matter! Is there anything we can help with? 🌟"
            )
        elif signal.signal_type == "negative_sentiment":
            intervention_type = "support_offer"
            message = "We appreciate your work. Open source is a team effort - we're here to support you! 🤝"
        elif signal.signal_type == "increased_response_time":
            intervention_type = "workload_reduction"
            message = "We can help distribute the workload. Let's chat about how we can make things easier! 💬"

        Intervention.objects.create(
            user=user,
            signal=signal,
            intervention_type=intervention_type,
            message=message,
            status="pending",
        )

        logger.info(f"Intervention triggered for {user.username}")

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
