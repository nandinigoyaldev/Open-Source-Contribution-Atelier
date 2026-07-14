from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        import apps.accounts.receivers  # noqa: F401
        import apps.accounts.signals  # noqa: F401

        try:
            from django_q.models import Schedule

            Schedule.objects.get_or_create(
                name="purge-expired-sessions-daily",
                defaults={
                    "func": "apps.accounts.tasks.purge_expired_sessions_task",
                    "schedule_type": Schedule.DAILY,
                },
            )
        except Exception:
            pass
