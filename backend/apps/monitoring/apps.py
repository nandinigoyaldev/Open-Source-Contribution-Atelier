from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.monitoring"
    verbose_name = "Monitoring"

    def ready(self):
        try:
            import apps.monitoring.celery_monitor  # noqa: F401
        except ImportError:
            pass
        try:
            from apps.monitoring.collectors import register_collectors

            register_collectors()
        except Exception:
            pass
