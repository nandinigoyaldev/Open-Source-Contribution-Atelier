"""
Admin configuration for events app.
"""

from django.contrib import admin
from .models import DomainEvent, EventSubscription, EventHandler


@admin.register(DomainEvent)
class DomainEventAdmin(admin.ModelAdmin):
    """
    Admin for DomainEvent model.
    """

    list_display = ["id", "event_name", "event_type", "status", "actor", "occurred_at"]
    list_filter = ["event_type", "status", "priority", "occurred_at"]
    search_fields = ["event_name", "event_type", "data"]
    readonly_fields = ["id", "created_at", "updated_at", "occurred_at", "processed_at"]
    fieldsets = (
        ("Event Info", {"fields": ("id", "event_type", "event_name", "version")}),
        ("Data", {"fields": ("data", "metadata")}),
        ("Target", {"fields": ("actor", "content_type", "object_id")}),
        ("Status", {"fields": ("status", "priority", "retry_count", "max_retries")}),
        (
            "Timestamps",
            {"fields": ("occurred_at", "processed_at", "created_at", "updated_at")},
        ),
        ("Errors", {"fields": ("last_error", "error_stack")}),
    )

    def has_add_permission(self, request):
        return False


@admin.register(EventSubscription)
class EventSubscriptionAdmin(admin.ModelAdmin):
    """
    Admin for EventSubscription model.
    """

    list_display = ["subscriber", "event_types", "is_active", "priority"]
    list_filter = ["is_active", "priority"]
    search_fields = ["subscriber"]


@admin.register(EventHandler)
class EventHandlerAdmin(admin.ModelAdmin):
    """
    Admin for EventHandler model.
    """

    list_display = [
        "name",
        "event_type",
        "status",
        "success_count",
        "error_count",
        "last_run",
    ]
    list_filter = ["status", "event_type"]
    search_fields = ["name", "handler_class"]
    readonly_fields = ["success_count", "error_count", "last_run"]
