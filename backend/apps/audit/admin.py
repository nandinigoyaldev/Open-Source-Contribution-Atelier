from django.contrib import admin
from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "actor",
        "resource_type",
        "resource_id",
        "correlation_id",
        "ip_address",
        "created_at",
    )
    list_filter = ("action", "resource_type", "created_at")
    search_fields = (
        "actor__username",
        "resource_id",
        "correlation_id",
        "ip_address",
        "user_agent",
    )
    readonly_fields = (
        "actor",
        "action",
        "resource_type",
        "resource_id",
        "before",
        "after",
        "correlation_id",
        "ip_address",
        "user_agent",
        "created_at",
        "extra",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
