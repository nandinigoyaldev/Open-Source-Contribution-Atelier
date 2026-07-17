from django.contrib import admin
from apps.core.models import AdminAuditLog

@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "timestamp", "ip_address")
    list_filter = ("action", "target_type", "timestamp")
    search_fields = ("actor__username", "action", "target_id", "ip_address")
    readonly_fields = ("actor", "action", "target_type", "target_id", "details", "timestamp", "ip_address")
    
    # Read-only permissions
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
