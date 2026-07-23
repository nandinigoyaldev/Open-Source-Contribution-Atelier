from django.db import models


class A11yIssue(models.Model):
    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("serious", "Serious"),
        ("moderate", "Moderate"),
        ("minor", "Minor"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    ]

    route = models.CharField(max_length=255)
    selector = models.TextField()
    violation_type = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.violation_type} on {self.route}"
