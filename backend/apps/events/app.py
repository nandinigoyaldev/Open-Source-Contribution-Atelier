"""
App configuration for events app.
"""

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.events'
    label = 'events'
    verbose_name = 'Domain Events'
    
    def ready(self):
        """
        Initialize event handlers when the app is ready.
        """
        try:
            from apps.events.registry import init_event_handlers
            init_event_handlers()
            logger.info("Events app initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize event handlers: {e}")