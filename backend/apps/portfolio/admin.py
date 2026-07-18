from django.contrib import admin
from .models import PortfolioTemplate, GeneratedPortfolio


@admin.register(PortfolioTemplate)
class PortfolioTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(GeneratedPortfolio)
class GeneratedPortfolioAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "format", "status", "created_at", "expires_at")
    list_filter = ("status", "format", "created_at")
    search_fields = ("user__username", "user__email", "id")
    readonly_fields = ("id", "created_at", "expires_at")
