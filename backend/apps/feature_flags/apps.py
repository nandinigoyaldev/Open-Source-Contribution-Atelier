from django.apps import AppConfig


class FeatureFlagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.feature_flags"
    label = "feature_flags"
