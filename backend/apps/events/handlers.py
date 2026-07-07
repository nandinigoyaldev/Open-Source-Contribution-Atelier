"""
Event handlers for processing domain events.
"""

import logging
from django.utils import timezone
from django.contrib.auth.models import User
from apps.events.models import DomainEvent

logger = logging.getLogger(__name__)


# ============================================================
# Progress Handlers
# ============================================================


def handle_lesson_completed(event: DomainEvent):
    """
    Handle LessonCompleted event.
    Updates progress, checks for module completion, and triggers streak.
    """
    from apps.progress.models import UserProgress
    from apps.events.services.event_bus import EventFactory

    data = event.data
    user_id = data["user_id"]
    lesson_id = data["lesson_id"]

    logger.info(f"Processing LessonCompleted for user {user_id}, lesson {lesson_id}")

    # Update progress
    progress, created = UserProgress.objects.get_or_create(
        user_id=user_id, lesson_id=lesson_id, defaults={"completed": True}
    )
    progress.completed = True
    progress.completed_at = timezone.now()
    progress.save()

    # Check if module is completed
    # ... (check all lessons in module)

    # Trigger other events
    # Example: if module completed, emit ModuleCompleted
    # EventFactory.create_module_completed(user, module)


def handle_quiz_completed(event: DomainEvent):
    """
    Handle QuizCompleted event.
    Updates quiz progress, checks for badge eligibility.
    """
    from apps.progress.models import QuizProgress
    from apps.badges.models import Badge, UserBadge
    from apps.events.services.event_bus import EventFactory

    data = event.data
    user_id = data["user_id"]
    quiz_id = data["quiz_id"]
    score = data["score"]
    passed = data["passed"]

    logger.info(
        f"Processing QuizCompleted for user {user_id}, quiz {quiz_id}, score {score}"
    )

    # Update quiz progress
    quiz_progress, created = QuizProgress.objects.get_or_create(
        user_id=user_id, quiz_id=quiz_id
    )
    quiz_progress.score = score
    quiz_progress.passed = passed
    quiz_progress.completed_at = timezone.now()
    quiz_progress.save()

    # Check for badge eligibility
    if passed:
        # Check if user qualifies for any badges
        user = User.objects.get(id=user_id)
        badges = Badge.objects.filter(condition_type="quiz", condition_value__lte=score)

        for badge in badges:
            user_badge, created = UserBadge.objects.get_or_create(
                user=user, badge=badge
            )
            if created:
                # Emit BadgeUnlocked event
                EventFactory.create_badge_unlocked(
                    user,
                    badge,
                    {"trigger": "quiz_completed", "quiz_id": quiz_id, "score": score},
                )


def handle_badge_unlocked(event: DomainEvent):
    """
    Handle BadgeUnlocked event.
    Triggers notifications and updates achievements.
    """
    from apps.notifications.services import NotificationService
    from apps.achievements.services import AchievementService

    data = event.data
    user_id = data["user_id"]
    badge_name = data["badge_name"]

    logger.info(f"Processing BadgeUnlocked for user {user_id}, badge {badge_name}")

    # Send notification
    user = User.objects.get(id=user_id)
    NotificationService.send_badge_unlocked_notification(user, badge_name)

    # Update achievements
    AchievementService.update_achievements(user)


def handle_certificate_generated(event: DomainEvent):
    """
    Handle CertificateGenerated event.
    Triggers email notification and achievement tracking.
    """
    from apps.notifications.services import NotificationService

    data = event.data
    user_id = data["user_id"]
    certificate_name = data["certificate_name"]

    logger.info(
        f"Processing CertificateGenerated for user {user_id}, certificate {certificate_name}"
    )

    # Send email notification
    user = User.objects.get(id=user_id)
    NotificationService.send_certificate_generated_notification(user, certificate_name)


def handle_streak_updated(event: DomainEvent):
    """
    Handle StreakUpdated event.
    Updates streak count and checks for streak milestones.
    """
    from apps.achievements.services import AchievementService

    data = event.data
    user_id = data["user_id"]
    streak_count = data["streak_count"]

    logger.info(f"Processing StreakUpdated for user {user_id}, count {streak_count}")

    # Update streak milestones
    user = User.objects.get(id=user_id)
    AchievementService.update_streak_milestones(user, streak_count)


def handle_module_completed(event: DomainEvent):
    """
    Handle ModuleCompleted event.
    Triggers certificate generation if all modules completed.
    """
    from apps.certificates.services import CertificateService
    from apps.events.services.event_bus import EventFactory

    data = event.data
    user_id = data["user_id"]
    module_id = data["module_id"]

    logger.info(f"Processing ModuleCompleted for user {user_id}, module {module_id}")

    # Check if all modules completed
    user = User.objects.get(id=user_id)
    # ... check all modules progress

    # If all modules completed, generate certificate
    # certificate = CertificateService.generate_certificate(user)
    # EventFactory.create_certificate_generated(user, certificate)


# ============================================================
# Analytics Handlers
# ============================================================


def handle_event_for_analytics(event: DomainEvent):
    """
    Generic handler for sending events to analytics.
    """
    from apps.analytics.services import AnalyticsService

    logger.info(f"Sending event {event.event_name} to analytics")
    AnalyticsService.track_event(event)


# ============================================================
# Notification Handlers
# ============================================================


def handle_event_for_notifications(event: DomainEvent):
    """
    Generic handler for sending notifications.
    """
    from apps.notifications.services import NotificationService

    logger.info(f"Sending notifications for event {event.event_name}")
    NotificationService.process_event(event)
