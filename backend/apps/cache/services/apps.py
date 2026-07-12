"""
App configuration for cache app.
"""

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CacheConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cache"
    label = "cache"
    verbose_name = "Cache Management"

    def ready(self):
        """
        Initialize cache system on app ready.
        """
        try:
            # Import signals to register them
            from apps.cache.services import cache_manager  # noqa

            logger.info("Cache system initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize cache system: {e}")
