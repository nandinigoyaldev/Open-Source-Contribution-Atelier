import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_secret():
    return secrets.token_hex(32)


class WebhookEndpoint(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webhooks",
        help_text="The user or organization that owns this webhook.",
    )
    target_url = models.URLField(
        max_length=512, help_text="The endpoint URL where webhook events will be sent."
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this webhook is currently enabled."
    )
    events = models.JSONField(
        default=list,
        help_text="A list of event types this webhook is subscribed to (e.g. ['lesson.completed', 'user.signup']).",
    )
    secret = models.CharField(
        max_length=64,
        default=generate_secret,
        help_text="Shared secret used to sign the webhook payloads.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.target_url} ({self.user.username})"


class WebhookDelivery(models.Model):
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    event_type = models.CharField(max_length=128)
    payload = models.JSONField()
    status = models.CharField(
        max_length=32,
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("retrying", "Retrying"),
            ("dead", "Dead"),
        ],
        default="pending",
    )
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    # Retry tracking
    attempt_count = models.PositiveIntegerField(
        default=0, help_text="Number of delivery attempts made so far."
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the next retry should be attempted.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Delivery {self.id} for {self.endpoint.target_url}"


class DeadLetterWebhook(models.Model):
    """
    Stores webhook deliveries that have permanently failed after all retries.
    Operators can inspect these and optionally requeue them via the admin
    or the `replay_dead_webhooks` management command.
    """

    delivery = models.OneToOneField(
        WebhookDelivery,
        on_delete=models.CASCADE,
        related_name="dead_letter",
        help_text="The original delivery that exhausted all retries.",
    )
    reason = models.TextField(
        help_text="The final error or non-2xx status that caused permanent failure."
    )
    replayed = models.BooleanField(
        default=False,
        help_text="Whether this entry has been manually requeued for replay.",
    )
    replayed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent replay attempt.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DLQ entry for delivery {self.delivery_id}"
