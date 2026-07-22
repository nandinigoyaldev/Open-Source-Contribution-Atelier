"""
App configuration for benchmark.
"""

from django.apps import AppConfig


class BenchmarkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.benchmark"
    label = "benchmark"
    verbose_name = "WebSocket Benchmark"
