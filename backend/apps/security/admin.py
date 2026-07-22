from django.contrib import admin

from .models import (
    AutoFixPR,
    VulnerabilityItem,
    VulnerabilityReport,
    VulnerabilitySuppression,
)


@admin.register(VulnerabilityReport)
class VulnerabilityReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "scan_date",
        "branch",
        "commit_sha",
        "total_vulnerabilities",
        "critical_count",
        "high_count",
    )
    search_fields = ("commit_sha", "branch")


@admin.register(VulnerabilityItem)
class VulnerabilityItemAdmin(admin.ModelAdmin):
    list_display = (
        "cve_id",
        "package_name",
        "installed_version",
        "fixed_version",
        "severity",
        "ecosystem",
        "status",
    )
    list_filter = ("severity", "ecosystem", "status")
    search_fields = ("cve_id", "package_name", "title")


@admin.register(VulnerabilitySuppression)
class VulnerabilitySuppressionAdmin(admin.ModelAdmin):
    list_display = ("cve_id", "package_name", "reason", "expires_at", "is_active")
    search_fields = ("cve_id", "package_name", "reason")


@admin.register(AutoFixPR)
class AutoFixPRAdmin(admin.ModelAdmin):
    list_display = ("pr_number", "pr_url", "status", "created_at")
    list_filter = ("status",)
