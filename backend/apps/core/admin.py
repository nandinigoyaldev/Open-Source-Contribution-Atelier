from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from apps.core.models import AdminAuditLog, PurgeLog

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

@admin.register(PurgeLog)
class PurgeLogAdmin(admin.ModelAdmin):
    list_display = ("model_name", "records_deleted", "execution_time", "duration_seconds")
    change_list_template = "core/admin/purge_log_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "cache-dashboard/",
                self.admin_site.admin_view(self.cache_dashboard_view),
                name="core_purgelog_cache_dashboard",
            ),
        ]
        return custom_urls + urls

    def cache_dashboard_view(self, request):
        active_tags = []
        try:
            from django_redis import get_redis_connection
            con = get_redis_connection("default")
            for k in con.scan_iter(match="cache_tag:*"):
                tag = k.decode("utf-8").replace("cache_tag:", "") if isinstance(k, bytes) else k.replace("cache_tag:", "")
                members = con.smembers(k)
                keys = [m.decode("utf-8") if isinstance(m, bytes) else m for m in members]
                active_tags.append({"tag": tag, "keys": keys})
        except Exception:
            from django.core.cache import cache
            if hasattr(cache, "_cache"):
                for k in list(cache._cache.keys()):
                    if k.startswith("cache_tag:"):
                        tag = k.replace("cache_tag:", "")
                        keys = list(cache.get(k, []))
                        active_tags.append({"tag": tag, "keys": keys})

        if request.method == "POST" and "invalidate_tag" in request.POST:
            tag_to_purge = request.POST.get("invalidate_tag")
            from apps.core.tasks import invalidate_tag_task
            invalidate_tag_task.delay(tag_to_purge)
            self.message_user(request, f"Purge task queued for tag: {tag_to_purge}")
            return redirect(request.path)

        context = dict(
            self.admin_site.each_context(request),
            active_tags=active_tags,
            title="Cache Invalidation Dashboard",
        )
        return render(request, "core/admin/cache_dashboard.html", context)

