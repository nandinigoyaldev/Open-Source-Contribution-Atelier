from django.contrib import admin

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "description")
    list_filter = ("enabled",)
    search_fields = ("name", "description")
    actions = ["enable_flags", "disable_flags"]

    @admin.action(description="Enable selected flags")
    def enable_flags(self, request, queryset):
        queryset.update(enabled=True)

    @admin.action(description="Disable selected flags")
    def disable_flags(self, request, queryset):
        queryset.update(enabled=False)
