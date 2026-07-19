"""
Celery tasks for onboarding monitoring.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.onboarding.models import OnboardingJourney, OnboardingMetric
from apps.onboarding.services.nudge_engine import NudgeEngine
from apps.onboarding.services.ml_predictor import OnboardingPredictor
import logging

logger = logging.getLogger(__name__)


@shared_task
def monitor_onboarding():
    """
    Monitor all active onboarding journeys.
    """
    logger.info("Starting onboarding monitoring")

    journeys = OnboardingJourney.objects.filter(status='active')
    engine = NudgeEngine()

    checked_count = 0
    nudged_count = 0

    for journey in journeys:
        try:
            engine.check_and_nudge(journey)
            checked_count += 1
            if journey.last_nudge_at:
                nudged_count += 1
        except Exception as e:
            logger.error(f"Error monitoring {journey.user.username}: {e}")

    logger.info(f"Monitored {checked_count} journeys, sent {nudged_count} nudges")
    return {'checked': checked_count, 'nudged': nudged_count}


@shared_task
def train_prediction_model():
    """
    Retrain the prediction model.
    """
    logger.info("Training prediction model")
    predictor = OnboardingPredictor()
    result = predictor.train_model()
    logger.info(f"Model training complete: {result}")
    return result


@shared_task
def update_onboarding_metrics():
    """
    Update daily onboarding metrics.
    """
    logger.info("Updating onboarding metrics")

    today = timezone.now().date()
    journeys = OnboardingJourney.objects.all()

    # Calculate metrics
    metrics = OnboardingMetric.objects.create(date=today)

    metrics.active_contributors = journeys.filter(status='active').count()
    metrics.new_contributors = journeys.filter(created_at__date=today).count()

    # Stage distribution
    metrics.discovery_count = journeys.filter(current_stage='discovery').count()
    metrics.setup_count = journeys.filter(current_stage='setup').count()
    metrics.first_issue_count = journeys.filter(current_stage='first_issue').count()
    metrics.pr_submitted_count = journeys.filter(current_stage='pr_submitted').count()
    metrics.merged_count = journeys.filter(current_stage='merged').count()

    # Drop-off rates
    total = journeys.count()
    if total > 0:
        metrics.discovery_dropoff = (metrics.discovery_count / total) * 100
        metrics.setup_dropoff = (metrics.setup_count / total) * 100
        metrics.first_issue_dropoff = (metrics.first_issue_count / total) * 100
        metrics.pr_dropoff = (metrics.pr_submitted_count / total) * 100

    # Average durations
    completed = journeys.filter(status='completed')
    if completed.exists():
        metrics.avg_discovery_duration = completed.aggregate(
            avg=models.Avg('discovery_duration')
        )['avg'] or 0
        metrics.avg_setup_duration = completed.aggregate(
            avg=models.Avg('setup_duration')
        )['avg'] or 0
        metrics.avg_first_issue_duration = completed.aggregate(
            avg=models.Avg('first_issue_duration')
        )['avg'] or 0
        metrics.avg_pr_duration = completed.aggregate(
            avg=models.Avg('pr_duration')
        )['avg'] or 0

        metrics.completion_rate = (completed.count() / total) * 100

    # Average health score
    metrics.average_health_score = journeys.aggregate(
        avg=models.Avg('health_score')
    )['avg'] or 0

    metrics.save()

    logger.info(f"Metrics updated for {today}")
    return {'date': str(today), 'metrics': metrics.id}