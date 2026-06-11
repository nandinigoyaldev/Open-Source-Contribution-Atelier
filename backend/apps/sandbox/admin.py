from django.contrib import admin
from .models import SandboxExecutionLog

@admin.register(SandboxExecutionLog)
class SandboxExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "command", "accepted", "score_delta", "created_at")
    list_filter = ("accepted", "created_at")
    search_fields = ("user__username", "command")
    readonly_fields = ("created_at",)
