import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .badge_evaluator import BadgeEvaluator

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def evaluate_user_badges_task(user_id):
    """
    Asynchronously evaluates and awards badges for a given user.
    """
    try:
        user = User.objects.get(id=user_id)
        BadgeEvaluator.evaluate(user)
    except User.DoesNotExist:
        logger.warning(
            f"User with id {user_id} does not exist. Badge evaluation skipped."
        )
    except Exception as e:
        logger.error(f"Error evaluating badges for user {user_id}: {e}")
