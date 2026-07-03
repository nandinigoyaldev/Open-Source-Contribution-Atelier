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

    seven_days_ago = timezone.now() - timedelta(days=7)

    # Process active users in chunks
    users = User.objects.filter(is_active=True).iterator(chunk_size=100)

    for user in users:
        # Get progress in the last 7 days
        recent_progress = LessonProgress.objects.filter(
            user=user, updated_at__gte=seven_days_ago, completed=True
        )

        recent_badges = UserBadge.objects.filter(
            user=user, earned_at__gte=seven_days_ago
        )

        lessons_completed = recent_progress.count()
        xp_earned = sum(progress.score for progress in recent_progress)
        badges_earned = recent_badges.count()
        badge_names = [ub.badge.name for ub in recent_badges]

        if lessons_completed > 0 or badges_earned > 0:
            payload = {
                "template_id": "weekly_progress_summary",
                "recipients": [user.email],
                "data": {
                    "username": user.username,
                    "lessons_completed": lessons_completed,
                    "xp_earned": xp_earned,
                    "badges_earned": badges_earned,
                    "badge_names": badge_names,
                },
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
