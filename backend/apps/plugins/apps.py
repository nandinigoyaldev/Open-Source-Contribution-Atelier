from django.apps import AppConfig

class PluginsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.plugins'

    def ready(self):
        # Scan and load active plugins on startup
        from .registry import registry
        registry.discover_and_sync()
        registry.load_active_plugins()
