from django.apps import AppConfig


class ChallengesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.challenges"

    def ready(self):
        try:
            import apps.challenges.signals
        except ImportError:
            pass
