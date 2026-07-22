from django.apps import AppConfig


class ProgressConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.progress"

    def ready(self):
        import apps.progress.signals  # noqa: F401

        # Register Django-Q schedule for weekly progress summary
        try:
            from django_q.models import Schedule

            Schedule.objects.get_or_create(
                name="send-weekly-progress-summary",
                defaults={
                    "func": "apps.progress.tasks.send_weekly_progress_summary",
                    "schedule_type": Schedule.WEEKLY,
                },
            )

            Schedule.objects.get_or_create(
                name="process-buffered-progress-updates",
                defaults={
                    "func": "apps.progress.tasks.process_buffered_progress_updates",
                    "schedule_type": Schedule.MINUTES,
                    "minutes": 1,
                },
            )
        except Exception:
            # Catch database programming/operational errors during migrations or tests
            pass
