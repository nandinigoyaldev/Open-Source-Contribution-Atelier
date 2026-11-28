import logging

logger = logging.getLogger(__name__)
from django.apps import AppConfig


class ProgressConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.progress"

    def ready(self):
        from django.db.models.signals import post_migrate

        import apps.progress.signals  # noqa: F401

        post_migrate.connect(self.setup_initial_data, sender=self)

    def setup_initial_data(self, sender, **kwargs):
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

            Schedule.objects.get_or_create(  # pyright: ignore[reportAttributeAccessIssue]
                name="apply-streak-freezes",
                defaults={
                    "func": "apps.progress.tasks.apply_streak_freezes_task",
                    "schedule_type": Schedule.HOURLY,
                },
            )
        except Exception as e:
            logger.warning("Caught exception: %s", e)
            # Catch database programming/operational errors during migrations or tests
            pass
