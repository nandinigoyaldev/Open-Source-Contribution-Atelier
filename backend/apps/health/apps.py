"""
App configuration for health checks.
"""

from django.apps import AppConfig


class HealthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.health"
    label = "health"
    verbose_name = "Health Checks"
