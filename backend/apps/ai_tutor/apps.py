import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AiTutorConfig(AppConfig):
    default_auto_field = (
        "django.db.models.BigAutoField"  # pyright: ignore[reportAssignmentType]
    )
    name = "apps.ai_tutor"

    def ready(self):
        from django.db.models.signals import post_migrate

        import apps.ai_tutor.signals  # noqa: F401

        post_migrate.connect(self.setup_schedules, sender=self)

    def setup_schedules(self, sender, **kwargs):
        try:
            from django_q.models import Schedule

            Schedule._default_manager.get_or_create(
                name="flush-ai-token-usage",
                defaults={
                    "func": "apps.ai_tutor.tasks.flush_ai_token_usage",
                    "schedule_type": Schedule.MINUTES,
                    "minutes": 1,
                },
            )
        except Exception as exc:
            logger.warning("Could not register the AI token flush schedule: %s", exc)
