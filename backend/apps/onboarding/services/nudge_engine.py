"""
Personalized nudge system for contributors.
"""

from django.utils import timezone
from datetime import timedelta
from apps.onboarding.models import OnboardingJourney, OnboardingNudge
from apps.onboarding.services.ml_predictor import OnboardingPredictor
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)


class NudgeEngine:
    """
    Personalized nudge engine for onboarding.
    """

    def __init__(self):
        self.predictor = OnboardingPredictor()

    def check_and_nudge(self, journey: OnboardingJourney):
        """
        Check journey and send nudges if needed.
        """
        # Calculate completion score
        probability, confidence = self.predictor.predict_completion(journey)
        journey.completion_score = probability * 100
        journey.save()

        # Check if nudge needed
        if probability < 0.5:
            self._send_encouragement_nudge(journey)

        # Check time in stage
        if journey.stage_started_at:
            time_in_stage = (timezone.now() - journey.stage_started_at).days
            if time_in_stage >= 3:
                self._send_reminder_nudge(journey)

        # Check for drop-off
        if self._is_dropping_off(journey):
            journey.is_dropped_off = True
            journey.dropped_off_at = timezone.now()
            journey.save()
            self._send_checkin_nudge(journey)

    def _send_encouragement_nudge(self, journey: OnboardingJourney):
        """Send encouragement nudge."""
        messages = [
            "You're making great progress! Keep going! 🚀",
            "Every journey starts with a single step. You've got this! 💪",
            "Your first contribution is closer than you think! 🌟",
            "Remember why you started. You're doing amazing! ✨",
        ]

        import random

        message = random.choice(messages)

        self._create_nudge(journey, "encouragement", message)

    def _send_reminder_nudge(self, journey: OnboardingJourney):
        """Send reminder nudge."""
        message = f"⏰ You've been at the '{journey.get_current_stage_display()}' stage for a while. Need any help getting unstuck?"

        self._create_nudge(journey, "reminder", message)

    def _send_checkin_nudge(self, journey: OnboardingJourney):
        """Send check-in nudge."""
        message = (
            "👋 Just checking in! How's your onboarding going? We're here to help!"
        )

        self._create_nudge(journey, "checkin", message)

    def _create_nudge(self, journey: OnboardingJourney, nudge_type: str, message: str):
        """Create and send nudge."""
        # Check if similar nudge was sent recently
        recent_nudge = OnboardingNudge.objects.filter(
            journey=journey,
            nudge_type=nudge_type,
            created_at__gte=timezone.now() - timedelta(days=1),
        ).exists()

        if recent_nudge:
            return

        nudge = OnboardingNudge.objects.create(
            journey=journey,
            nudge_type=nudge_type,
            message=message,
            is_sent=True,
            sent_at=timezone.now(),
        )

        # Update journey
        if not journey.last_nudge_at:
            journey.last_nudge_at = timezone.now()
            journey.save()

        # Send WebSocket notification
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{journey.user.id}",
                {
                    "type": "nudge",
                    "data": {
                        "id": str(nudge.id),
                        "type": nudge_type,
                        "message": message,
                    },
                },
            )
        except Exception as e:
            logger.error(f"WebSocket nudge failed: {e}")

        logger.info(f"Nudge sent to {journey.user.username}: {nudge_type}")

    def _is_dropping_off(self, journey: OnboardingJourney) -> bool:
        """Check if journey is dropping off."""
        # No activity for 7 days
        last_event = (
            JourneyEvent.objects.filter(journey=journey).order_by("-created_at").first()
        )

        if last_event:
            days_since = (timezone.now() - last_event.created_at).days
            return days_since >= 7

        # No events at all after 14 days
        if journey.created_at:
            days_since = (timezone.now() - journey.created_at).days
            return days_since >= 14

        return False
