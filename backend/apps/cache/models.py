"""
Cache dependency tracking models.
"""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone


class CacheDependency(models.Model):
    """
    Tracks dependencies between models for cache invalidation.
    """

    # Source (what depends on)
    source_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="cache_source_dependencies"
    )
    source_object_id = models.PositiveIntegerField()
    source_object = GenericForeignKey("source_content_type", "source_object_id")

    # Target (what is depended on)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="cache_target_dependencies"
    )
    target_object_id = models.PositiveIntegerField()
    target_object = GenericForeignKey("target_content_type", "target_object_id")

    # Cache key that depends on these objects
    cache_key = models.CharField(max_length=500, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["source_content_type", "source_object_id"], name="idx_source_content_types"),
            models.Index(fields=["target_content_type", "target_object_id"], name="idx_target_content_typet"),
            models.Index(fields=["cache_key"], name="idx_cache_key"),
        ]
        unique_together = [
            [
                "source_content_type",
                "source_object_id",
                "target_content_type",
                "target_object_id",
                "cache_key",
            ]
        ]

    def __str__(self):
        return f"{self.source_object} -> {self.target_object} ({self.cache_key})"


class CacheConfig(models.Model):
    """
    Configuration for cache strategies per model.
    """

    STRATEGY_CHOICES = [
        ("write_through", "Write-Through"),
        ("write_around", "Write-Around"),
        ("write_back", "Write-Back"),
        ("stale_while_revalidate", "Stale-While-Revalidate"),
    ]

    model_name = models.CharField(max_length=100, unique=True)
    strategy = models.CharField(
        max_length=50, choices=STRATEGY_CHOICES, default="write_through"
    )
    ttl = models.IntegerField(default=300)  # Seconds
    max_size = models.IntegerField(default=1000)  # Max items
    warm_on_startup = models.BooleanField(default=False)
    warm_queries = models.JSONField(default=list)  # Queries to warm cache
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.model_name} - {self.strategy}"
