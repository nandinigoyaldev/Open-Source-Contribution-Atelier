import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class PortfolioTemplate(models.Model):
    """
    Templates for generating portfolios.
    Provides styling configurations or predefined layouts.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class GeneratedPortfolio(models.Model):
    """
    Tracks a user's generated portfolio report.
    """

    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        HTML = "html", "HTML"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generated_portfolios",
    )
    template = models.ForeignKey(
        PortfolioTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    format = models.CharField(max_length=10, choices=Format.choices, default=Format.PDF)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    sections_included = models.JSONField(
        default=dict,
        help_text="Stores which sections were included (e.g. {'badges': True, 'projects': False})",
    )

    file = models.FileField(upload_to="portfolios/", null=True, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="idx_userstatus"),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Default expiration is 7 days from creation
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Portfolio for {self.user.username} ({self.format}) - {self.status}"
