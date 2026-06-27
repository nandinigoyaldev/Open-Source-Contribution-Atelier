from django.contrib import admin

from .models import MentorProfile


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "get_assigned_lesson_count")
    search_fields = ("user__username", "user__email")
    filter_horizontal = ("assigned_lessons",)

    def get_queryset(self, request):
        from django.db.models import Count

        qs = super().get_queryset(request)
        return qs.annotate(_assigned_lesson_count=Count("assigned_lessons"))

    @admin.display(description="Assigned lessons", ordering="_assigned_lesson_count")
    def get_assigned_lesson_count(self, obj: MentorProfile) -> int:
        return getattr(obj, "_assigned_lesson_count", obj.assigned_lessons.count())


from django.contrib.admin.models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for Django's built-in LogEntry model.
    This tracks all CRUD operations performed by staff members in the admin interface.
    """

    date_hierarchy = "action_time"

    list_filter = [
        "user",
        "content_type",
        "action_flag",
    ]

    search_fields = [
        "object_repr",
        "change_message",
    ]

    list_display = [
        "action_time",
        "user",
        "content_type",
        "object_repr",
        "action_flag",
    ]

    # Audit trail integrity - make it strictly read-only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        # Allow staff to view the logs
        return request.user.is_staff
