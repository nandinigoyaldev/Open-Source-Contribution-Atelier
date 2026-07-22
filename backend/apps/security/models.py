from django.db import models
from django.utils import timezone


class VulnerabilityReport(models.Model):
    scan_date = models.DateTimeField(default=timezone.now)
    commit_sha = models.CharField(max_length=64, blank=True, default="")
    branch = models.CharField(max_length=128, blank=True, default="main")
    ecosystem = models.CharField(max_length=64, default="ALL")
    total_vulnerabilities = models.IntegerField(default=0)
    critical_count = models.IntegerField(default=0)
    high_count = models.IntegerField(default=0)
    medium_count = models.IntegerField(default=0)
    low_count = models.IntegerField(default=0)
    summary_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scan_date"]

    def __str__(self):
        return f"VulnerabilityReport({self.id}, {self.scan_date.strftime('%Y-%m-%d %H:%M')})"


class VulnerabilityItem(models.Model):
    SEVERITY_CHOICES = [
        ("CRITICAL", "Critical"),
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
    ]
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("FIX_PENDING", "Fix Pending"),
        ("RESOLVED", "Resolved"),
        ("SUPPRESSED", "Suppressed"),
    ]

    report = models.ForeignKey(
        VulnerabilityReport, on_delete=models.CASCADE, related_name="items"
    )
    cve_id = models.CharField(max_length=64)
    package_name = models.CharField(max_length=128)
    installed_version = models.CharField(max_length=64)
    fixed_version = models.CharField(max_length=64, blank=True, default="")
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES)
    ecosystem = models.CharField(max_length=32, default="python")  # python, npm, docker
    title = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="OPEN")
    suppressed_until = models.DateField(null=True, blank=True)
    suppression_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-severity", "cve_id"]

    def __str__(self):
        return f"{self.cve_id} - {self.package_name} ({self.severity})"


class VulnerabilitySuppression(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("REVOKED", "Revoked"),
    ]

    cve_id = models.CharField(max_length=64)
    package_name = models.CharField(max_length=128, blank=True, default="*")
    reason = models.TextField()
    expires_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        if self.expires_at < timezone.now().date():
            return False
        return True

    def __str__(self):
        return f"Suppression({self.cve_id}, expires={self.expires_at})"


class AutoFixPR(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("MERGED", "Merged"),
        ("CLOSED", "Closed"),
    ]

    pr_number = models.IntegerField()
    pr_url = models.URLField(max_length=500)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="OPEN")
    packages_updated = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AutoFixPR #{self.pr_number} ({self.status})"
