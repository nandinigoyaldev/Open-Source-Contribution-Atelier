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
