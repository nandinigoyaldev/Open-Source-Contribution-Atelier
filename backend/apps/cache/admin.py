"""
Admin configuration for cache app.
"""

from django.contrib import admin
from .models import CacheDependency, CacheConfig


@admin.register(CacheDependency)
class CacheDependencyAdmin(admin.ModelAdmin):
    """
    Admin for CacheDependency model.
    """

    list_display = ["cache_key", "source_object", "target_object", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["cache_key"]
    raw_id_fields = ["source_content_type", "target_content_type"]


@admin.register(CacheConfig)
class CacheConfigAdmin(admin.ModelAdmin):
    """
    Admin for CacheConfig model.
    """

    list_display = ["model_name", "strategy", "ttl", "warm_on_startup", "is_active"]
    list_filter = ["strategy", "warm_on_startup", "is_active"]
    search_fields = ["model_name"]
    fieldsets = (
        (
            "Model Configuration",
            {"fields": ("model_name", "strategy", "ttl", "max_size")},
        ),
        ("Warming Configuration", {"fields": ("warm_on_startup", "warm_queries")}),
        ("Status", {"fields": ("is_active",)}),
    )
