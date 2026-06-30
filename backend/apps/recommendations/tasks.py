from celery import shared_task
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from .engine import RecommendationEngine

@shared_task
def generate_user_recommendations(user_id):
    try:
        user = User.objects.get(id=user_id)
        engine = RecommendationEngine(user)
        engine.generate_recommendations()
    except ObjectDoesNotExist:
        pass
