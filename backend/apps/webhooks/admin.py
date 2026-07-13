from django.contrib import admin
from django.utils import timezone

from .models import DeadLetterWebhook, WebhookDelivery, WebhookEndpoint
from .tasks import replay_delivery


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("target_url", "user", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("target_url", "user__username")


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "endpoint",
        "event_type",
        "status",
        "attempt_count",
        "next_retry_at",
        "created_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("endpoint__target_url", "event_type")
    readonly_fields = ("attempt_count", "next_retry_at", "status_code", "response_body")


@admin.action(description="Replay selected DLQ entries")
def replay_selected_dlq(modeladmin, request, queryset):
    for entry in queryset:
        replay_delivery(entry.id)
    modeladmin.message_user(
        request, f"Queued {queryset.count()} delivery/deliveries for replay."
    )


@admin.register(DeadLetterWebhook)
class DeadLetterWebhookAdmin(admin.ModelAdmin):
    list_display = ("id", "delivery", "replayed", "replayed_at", "created_at")
    list_filter = ("replayed",)
    readonly_fields = ("delivery", "reason", "replayed", "replayed_at", "created_at")
    actions = [replay_selected_dlq]
