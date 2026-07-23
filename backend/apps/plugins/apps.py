from django.apps import AppConfig


class PluginsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.plugins"

    def ready(self):
        # Scan and load active plugins on startup
        from django.db.utils import OperationalError, ProgrammingError
        from .registry import registry

        try:
            registry.discover_and_sync()
            registry.load_active_plugins()
        except (OperationalError, ProgrammingError):
            pass
