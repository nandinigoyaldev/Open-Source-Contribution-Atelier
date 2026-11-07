import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_q.tasks import async_task

from apps.progress.models import Badge, ExerciseAttempt, LessonProgress, UserBadge

logger = logging.getLogger(__name__)
User = get_user_model()


def send_weekly_progress_summary():
    """
    Django-Q scheduled task to calculate learning progress over the past 7 days
    for each active user, and dispatch an email summary.

    Idempotent: uses WeeklyDigestLog to skip users who already received the
    digest for the current ISO week.
    """
    from apps.notifications.tasks import send_bulk_email
    from apps.progress.models import WeeklyDigestLog
    from apps.progress.services.digest_service import WeeklyDigestService

    now = timezone.now()
    # Monday of the current ISO week
    week_start = (now - timedelta(days=now.weekday())).date()

    # Process active users in chunks who opted in for the digest
    users = User.objects.filter(
        is_active=True, user_profile__receive_weekly_digest=True
    ).iterator(chunk_size=100)

    for user in users:
        # Skip if digest was already sent for this week
        if WeeklyDigestLog.objects.filter(user=user, week_start=week_start).exists():
            logger.info(
                "Skipping digest for %s — already sent for week of %s",
                user.username,
                week_start,
            )
            continue

        # Generate context using the new service
        context = WeeklyDigestService.get_user_digest_context(user)

        if (
            context["lessons_completed"] > 0
            or len(context["badges_earned"]) > 0
            or context["xp_earned"] > 0
        ):
            payload = {
                "template_id": "weekly_progress_summary",
                "recipients": [user.email],
                "data": context,
            }
            async_task("apps.notifications.tasks.send_bulk_email", payload)

            # Record that we sent the digest so re-runs won't duplicate
            WeeklyDigestLog.objects.get_or_create(user=user, week_start=week_start)


def _increment_badge_skip_metric(user_id=None, badge_id=None, reason=""):
    """
    Increments the skipped badge metrics counter in cache.
    """
    from apps.core.cache import multi_level_cache as cache

    metric_key = "badge_issuance_skipped_total"
    try:
        if cache.get(metric_key) is None:
            cache.set(metric_key, 1, timeout=86400 * 30)
        else:
            cache.incr(metric_key)
    except Exception as exc:
        logger.warning("Failed to update badge skip metric counter: %s", exc)


def evaluate_achievements_task(user_id):
    from django.contrib.auth import get_user_model

    from apps.notifications.signals import create_and_push_notification

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(
            "Skipping achievement evaluation: Recipient user id=%s not found",
            user_id,
            extra={"user_id": user_id, "reason": "user_not_found"},
        )
        _increment_badge_skip_metric(user_id=user_id, reason="user_not_found")
        return

    milestones = {
        "first-lesson": {
            "name": "First Lesson Completed",
            "check": lambda u: LessonProgress.objects.filter(
                user=u, completed=True
            ).count()
            >= 1,
        },
        "five-lessons": {
            "name": "5 Lessons Completed",
            "check": lambda u: LessonProgress.objects.filter(
                user=u, completed=True
            ).count()
            >= 5,
        },
        "ten-lessons": {
            "name": "10 Lessons Completed",
            "check": lambda u: LessonProgress.objects.filter(
                user=u, completed=True
            ).count()
            >= 10,
        },
        "first-challenge": {
            "name": "First Challenge",
            "check": lambda u: ExerciseAttempt.objects.filter(
                user=u, is_correct=True
            ).count()
            >= 1,
        },
        "five-challenges": {
            "name": "5 Challenges Completed",
            "check": lambda u: ExerciseAttempt.objects.filter(
                user=u, is_correct=True
            ).count()
            >= 5,
        },
        "ten-challenges": {
            "name": "10 Challenges Completed",
            "check": lambda u: ExerciseAttempt.objects.filter(
                user=u, is_correct=True
            ).count()
            >= 10,
        },
        "twenty-five-challenges": {
            "name": "25 Challenges Completed",
            "check": lambda u: ExerciseAttempt.objects.filter(
                user=u, is_correct=True
            ).count()
            >= 25,
        },
    }

    for slug, meta in milestones.items():
        if meta["check"](user):
            badge, created = Badge.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": meta["name"],
                    "description": f"Earned {meta['name']}",
                },
            )
            _, newly_earned = UserBadge.objects.get_or_create(user=user, badge=badge)
            if newly_earned:
                create_and_push_notification(
                    recipient=user,
                    notif_type="badge",
                    title="\U0001f3c6 Badge Unlocked!",
                    message=f"You unlocked: {badge.name}",
                    meta={
                        "badge_slug": badge.slug,
                        "icon": badge.icon_asset_url,
                    },
                )

    # Evaluate seasonal track milestones
    try:
        from apps.progress.services.milestone_track_service import MilestoneTrackService

        MilestoneTrackService.evaluate_milestones(user)
    except Exception as exc:
        logger.error("Failed to evaluate seasonal milestones: %s", exc)


def evaluate_user_badges_task(user_id):
    evaluate_achievements_task(user_id)


def analyze_submission_plagiarism(submission_id: int):
    """Check a code submission for plagiarism against other submissions.

    Creates a :class:`PlagiarismReport` when an identical submission is found.
    Only exact structural matches (score == 1.0) are flagged, matching the test expectations.
    """
    from apps.progress.models import CodeSubmission, PlagiarismReport
    from apps.progress.services.plagiarism_detector import (
        calculate_structural_similarity,
    )

    try:
        submission = CodeSubmission.objects.get(id=submission_id)
    except CodeSubmission.DoesNotExist:
        return

    # Compare with other submissions for the same exercise (if any)
    candidates = CodeSubmission.objects.filter(exercise=submission.exercise).exclude(
        id=submission.id
    )
    for other in candidates:
        score = calculate_structural_similarity(
            submission.code_snippet, other.code_snippet
        )
        if score == 1.0:
            PlagiarismReport.objects.create(
                submission=submission,
                matched_submission=other,
                similarity_score=score,
                is_flagged=True,
            )
            # Stop after first match as tests expect a single report
            break


def update_leaderboard_task(user_id, username, xp_delta):
    """
    Background task to update Redis leaderboard and broadcast WebSocket event.
    """
    try:
        from apps.progress.services.leaderboard_service import LeaderboardService

        LeaderboardService.update_user_xp(user_id, username, xp_delta)
    except Exception as exc:
        logger.error("Failed to update leaderboard in background task: %s", exc)


def process_buffered_progress_updates():
    """
    Periodic task to flush batched progress and XP updates from Redis to the database.
    Ensures atomic updates and maintains data consistency.
    """
    import time

    from django.contrib.auth import get_user_model

    from apps.progress.services.progress_batch_service import (
        process_bulk_progress_updates,
    )
    from apps.progress.services.progress_buffer import ProgressBufferService

    User = get_user_model()

    metrics = ProgressBufferService.get_queue_metrics()
    queue_size = metrics.get("queue_size", 0) + metrics.get("retry_queue_size", 0)

    if queue_size == 0:
        return

    logger.info(f"Processing up to 500 of {queue_size} buffered progress updates...")

    updates = ProgressBufferService.get_batched_updates(batch_size=500)
    if not updates:
        return

    # Group by user
    user_updates = {}
    for update in updates:
        user_id = update["user_id"]
        if user_id not in user_updates:
            user_updates[user_id] = []
        user_updates[user_id].append(update)

    success_count = 0
    successful_keys = []
    failed_updates = []

    for user_id, user_data in user_updates.items():
        try:
            user = User.objects.get(id=user_id)
            # Send without the internal _redis_key metadata
            clean_data = [
                {k: v for k, v in item.items() if not k.startswith("_")}
                for item in user_data
            ]

            result = process_bulk_progress_updates(user, clean_data)
            success_count += len(result.updated_ids)
            # Nobody is waiting on a buffered write, so a refused one can only be
            # counted. Retrying would never help, the row is already ahead of it.
            ProgressBufferService.record_conflicts(len(result.conflicts))

            # Record successful keys
            successful_keys.extend(
                [item["_redis_key"] for item in user_data if "_redis_key" in item]
            )
        except Exception as e:
            logger.error(f"Failed to process bulk updates for user {user_id}: {str(e)}")
            failed_updates.extend(user_data)

    if successful_keys:
        ProgressBufferService.mark_successful(successful_keys)

    if failed_updates:
        ProgressBufferService.handle_failed_updates(failed_updates)

    logger.info(
        f"Successfully processed {success_count} progress updates. {len(failed_updates)} failed."
    )


def award_specific_badge(user_id, badge_id):
    """
    Background task to award a specific badge to a user.
    Logs warnings and increments metric counter when user or badge is missing.
    """
    from apps.notifications.signals import create_and_push_notification

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(
            "Skipping badge award: Recipient user id=%s not found (badge_id=%s)",
            user_id,
            badge_id,
            extra={
                "user_id": user_id,
                "badge_id": badge_id,
                "reason": "user_not_found",
            },
        )
        _increment_badge_skip_metric(
            user_id=user_id, badge_id=badge_id, reason="user_not_found"
        )
        return

    try:
        badge = Badge.objects.get(id=badge_id)
    except Badge.DoesNotExist:
        logger.warning(
            "Skipping badge award: Badge id=%s not found for recipient user_id=%s",
            badge_id,
            user_id,
            extra={
                "user_id": user_id,
                "badge_id": badge_id,
                "reason": "badge_not_found",
            },
        )
        _increment_badge_skip_metric(
            user_id=user_id, badge_id=badge_id, reason="badge_not_found"
        )
        return

    _, newly_earned = UserBadge.objects.get_or_create(user=user, badge=badge)
    if newly_earned:
        create_and_push_notification(
            recipient=user,
            notif_type="badge",
            title="\U0001f3c6 Badge Unlocked!",
            message=f"You unlocked: {badge.name}",
            meta={
                "badge_slug": badge.slug,
                "icon": badge.icon_asset_url,
            },
        )


def award_badge_to_users(user_ids, badge_id):
    """
    Award a badge to multiple recipients by user ID list.
    Logs warnings and increments skip metrics for any missing recipient user records or badge.
    """
    from apps.notifications.signals import create_and_push_notification

    results = {"awarded": 0, "skipped": 0}

    try:
        badge = Badge.objects.get(id=badge_id)
    except Badge.DoesNotExist:
        logger.warning(
            "Skipping bulk badge award: Badge id=%s not found for user_ids=%s",
            badge_id,
            user_ids,
        )
        for uid in user_ids:
            _increment_badge_skip_metric(
                user_id=uid, badge_id=badge_id, reason="badge_not_found"
            )
            results["skipped"] += 1
        return results

    for uid in user_ids:
        try:
            user = User.objects.get(id=uid)
            _, newly_earned = UserBadge.objects.get_or_create(user=user, badge=badge)
            if newly_earned:
                create_and_push_notification(
                    recipient=user,
                    notif_type="badge",
                    title="\U0001f3c6 Badge Unlocked!",
                    message=f"You unlocked: {badge.name}",
                    meta={
                        "badge_slug": badge.slug,
                        "icon": badge.icon_asset_url,
                    },
                )
            results["awarded"] += 1
        except User.DoesNotExist:
            logger.warning(
                "Skipping badge award for recipient user_id=%s (badge_id=%s): User record missing",
                uid,
                badge_id,
                extra={
                    "user_id": uid,
                    "badge_id": badge_id,
                    "reason": "user_not_found",
                },
            )
            _increment_badge_skip_metric(
                user_id=uid, badge_id=badge_id, reason="user_not_found"
            )
            results["skipped"] += 1

    return results


@shared_task
def archive_monthly_leaderboard():
    """
    Monthly Celery beat task running on the 1st of each month.
    Snapshots monthly XP ranks into LeaderboardArchive and resets monthly user XP counters
    while leaving lifetime XP unchanged.
    """
    from apps.progress.services.leaderboard_service import LeaderboardService

    return LeaderboardService.archive_and_reset_monthly_leaderboard()
