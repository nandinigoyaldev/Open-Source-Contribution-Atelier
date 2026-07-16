from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.conf import settings
import json
import os
from apps.core.models import PurgeLog, AdminAuditLog


@admin.register(PurgeLog)
class PurgeLogAdmin(admin.ModelAdmin):
    list_display = (
        "model_name",
        "records_deleted",
        "execution_time",
        "duration_seconds",
    )
    change_list_template = "core/admin/purge_log_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "search-logs/",
                self.admin_site.admin_view(self.search_logs_view),
                name="search_logs",
            ),
        ]
        return custom_urls + urls

    def search_logs_view(self, request):
        request_id = request.GET.get("request_id", "").strip()
        log_entries = []

        if request_id:
            log_file_path = os.path.join(settings.BASE_DIR, "audit.log")
            if os.path.exists(log_file_path):
                with open(log_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if request_id in line:
                            try:
                                log_entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                log_entries.append({"message": line.strip()})

        context = dict(
            self.admin_site.each_context(request),
            request_id=request_id,
            log_entries=log_entries,
            title="Search Request Logs",
        )
        return render(request, "core/admin/search_logs.html", context)


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
