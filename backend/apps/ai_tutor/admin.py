from django.contrib import admin

from .models import AITokenBudgetOverride, AITokenOrganizationPool, AITokenUsageLedger


@admin.register(AITokenUsageLedger)
class AITokenUsageLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "updated_at",
    )
    list_filter = ("date",)
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("updated_at",)
    date_hierarchy = "date"


@admin.register(AITokenBudgetOverride)
class AITokenBudgetOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "daily_token_limit", "expires_at", "reason", "updated_at")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email", "reason")
    raw_id_fields = ("user",)


@admin.register(AITokenOrganizationPool)
class AITokenOrganizationPoolAdmin(admin.ModelAdmin):
    list_display = ("organization", "daily_token_limit", "is_active", "updated_at")
    list_filter = ("is_active",)
    list_select_related = ("organization",)
    search_fields = ("organization__name",)
    raw_id_fields = ("organization",)
