"""
Celery tasks for burnout detection.
"""

from celery import shared_task
from django.utils import timezone
from apps.burnout_detection.models import ContributorActivity, BurnoutSignal, Intervention
from apps.burnout_detection.services.burnout_detector import BurnoutDetector
from apps.burnout_detection.services.sentiment_analyzer import SentimentAnalyzer
import logging

logger = logging.getLogger(__name__)


@shared_task
def detect_burnout():
    """
    Detect burnout in all contributors.
    """
    logger.info("Starting burnout detection")

    activities = ContributorActivity.objects.all()
    detector = BurnoutDetector()

    detected_count = 0
    critical_count = 0

    for activity in activities:
        try:
            result = detector.detect_burnout(activity)
            
            if result['needs_intervention']:
                detected_count += 1
                if result['risk_level'] == 'critical':
                    critical_count += 1
                
                # Create signals
                for signal_data in result['signals']:
                    BurnoutSignal.objects.create(
                        user=activity.user,
                        signal_type=signal_data['type'],
                        severity=signal_data['severity'],
                        description=signal_data['description']
                    )
                
                # Trigger intervention
                trigger_intervention.delay(activity.user.id)
                
        except Exception as e:
            logger.error(f"Error detecting burnout for {activity.user.username}: {e}")

    logger.info(f"Detected {detected_count} burnout cases ({critical_count} critical)")
    return {'detected': detected_count, 'critical': critical_count}


@shared_task
def trigger_intervention(user_id: int):
    """
    Trigger intervention for a user.
    """
    from django.contrib.auth import get_user_model

User = get_user_model()
    from apps.burnout_detection.models import Intervention, BurnoutSignal
    
    try:
        user = User.objects.get(id=user_id)
        signal = BurnoutSignal.objects.filter(user=user, is_resolved=False).first()
        
        if not signal:
            return
        
        # Determine intervention type
        intervention_type = 'encouragement'
        message = "We've noticed you've been working hard. Take a break and recharge! 💪"
        
        if signal.signal_type == 'declining_activity':
            intervention_type = 'encouragement'
            message = "Your contributions matter! Is there anything we can help with? 🌟"
        elif signal.signal_type == 'negative_sentiment':
            intervention_type = 'support_offer'
            message = "We appreciate your work. Open source is a team effort - we're here to support you! 🤝"
        elif signal.signal_type == 'increased_response_time':
            intervention_type = 'workload_reduction'
            message = "We can help distribute the workload. Let's chat about how we can make things easier! 💬"
        
        Intervention.objects.create(
            user=user,
            signal=signal,
            intervention_type=intervention_type,
            message=message,
            status='pending'
        )
        
        logger.info(f"Intervention triggered for {user.username}")
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")