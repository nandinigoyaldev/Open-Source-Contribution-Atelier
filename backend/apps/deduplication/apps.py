"""
App configuration for deduplication.
"""

from django.apps import AppConfig


class DeduplicationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.deduplication"
    label = "deduplication"
    verbose_name = "Request Deduplication"
