from django.apps import AppConfig


class ProgressConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.progress"

    def ready(self):
        import apps.progress.signals  # noqa: F401
