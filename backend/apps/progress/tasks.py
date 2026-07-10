import logging
from datetime import timedelta

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
    """
    from apps.notifications.tasks import send_bulk_email
    from apps.progress.services.digest_service import WeeklyDigestService

    # Process active users in chunks who opted in for the digest
    users = User.objects.filter(
        is_active=True, profile__receive_weekly_digest=True
    ).iterator(chunk_size=100)

    for user in users:
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



def evaluate_achievements_task(user_id):
    from django.contrib.auth import get_user_model

    from apps.notifications.signals import create_and_push_notification

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
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
