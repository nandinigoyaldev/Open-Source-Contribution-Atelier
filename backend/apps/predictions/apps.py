import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PredictionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.predictions"
    verbose_name = "PR Review Delay Predictions"

    def ready(self):
        # App initialization logic. DB writes and heavy ML model fitting
        # should be executed via management commands or scheduled background tasks
        # rather than blocking process boot / migrate commands.
        pass
