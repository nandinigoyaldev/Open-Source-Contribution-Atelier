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
