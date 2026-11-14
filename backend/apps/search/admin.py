from django.contrib import admin

from .models import SearchIndexFailure


@admin.register(SearchIndexFailure)
class SearchIndexFailureAdmin(admin.ModelAdmin):
    list_display = (
        "document_id",
        "operation",
        "content_type",
        "object_id",
        "attempts",
        "last_failed_at",
    )
    list_filter = ("operation", "content_type")
    search_fields = ("document_id", "last_error")
    readonly_fields = (
        "document_id",
        "content_type",
        "object_id",
        "operation",
        "attempts",
        "last_error",
        "first_failed_at",
        "last_failed_at",
    )

    def has_add_permission(self, request):
        return False
