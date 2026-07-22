"""
App configuration for profiler.
"""

from django.apps import AppConfig


class ProfilerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profiler"
    label = "profiler"
    verbose_name = "Performance Profiler"
