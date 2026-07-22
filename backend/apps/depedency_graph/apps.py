"""
App configuration for dependency graph.
"""

from django.apps import AppConfig


class DependencyGraphConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dependency_graph"
    label = "dependency_graph"
    verbose_name = "Dependency Graph"
