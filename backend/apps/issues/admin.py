from django.contrib import admin
from django.utils.html import format_html

from apps.issues.models import IssueReport


@admin.register(IssueReport)
class IssueReportAdmin(admin.ModelAdmin):
    list_display = ("title", "issue_type", "status", "user", "created_at")
    list_filter = ("status", "issue_type", "created_at")
    search_fields = ("title", "description", "url_path")
    readonly_fields = ("created_at", "updated_at", "image_preview")

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-width: 300px; height: auto;" /></a>',
                obj.image.url,
            )
        return "No Image"

    image_preview.short_description = "Image Preview"
