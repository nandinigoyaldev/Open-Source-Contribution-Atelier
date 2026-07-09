from django.apps import AppConfig


class CacheConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cache"

    def ready(self):
        # Import signals to register them
        from .services import cache_manager
        