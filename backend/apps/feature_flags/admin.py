"""
Admin configuration for feature flags.

Note: an earlier revision of this file (PR #920) registered admin classes
for `Experiment` and `FeatureFlagAuditLog`, and referenced many fields on
`FeatureFlag` (status, strategy, targeting, analytics counters, etc.) that
were never actually added to the model in models.py. That mismatch broke
Django's admin autodiscovery entirely, since the import at the top of this
file failed for every management command, not just `runserver`.

This revision registers only what the current `FeatureFlag` model actually
has (`name`, `enabled`, `description`). A/B testing (`Experiment`) and audit
logging (`FeatureFlagAuditLog`) should be reintroduced in a future PR once
those models, their fields, and their migrations are designed and land
together with the admin code that depends on them.
"""

from django.contrib import admin

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """Admin interface for the FeatureFlag model."""

    list_display = ("name", "enabled", "description_short", "id")
    list_filter = ("enabled",)
    search_fields = ("name", "description")
    list_per_page = 50

    fieldsets = (
        (
            "Feature Flag",
            {
                "fields": ("name", "enabled", "description"),
            },
        ),
    )

    actions = ["enable_flags", "disable_flags"]

    @admin.action(description="Enable selected flags")
    def enable_flags(self, request, queryset):
        updated = queryset.update(enabled=True)
        FeatureFlag.objects.invalidate_cache()
        self.message_user(request, f"Enabled {updated} flag(s).")

    @admin.action(description="Disable selected flags")
    def disable_flags(self, request, queryset):
        updated = queryset.update(enabled=False)
        FeatureFlag.objects.invalidate_cache()
        self.message_user(request, f"Disabled {updated} flag(s).")

    def description_short(self, obj):
        """Truncate description for the list view."""
        if obj.description and len(obj.description) > 60:
            return obj.description[:60] + "..."
        return obj.description

    description_short.short_description = "Description"
"""
Admin configuration for feature flags with A/B testing and advanced management.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "description_short")
    list_filter = ("enabled",)
    search_fields = ("name", "description")

    def description_short(self, obj):
        if len(obj.description) > 50:
            return obj.description[:50] + "..."
        return obj.description

    description_short.short_description = "Description"
