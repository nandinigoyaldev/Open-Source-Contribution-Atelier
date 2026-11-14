import datetime

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


def default_channel_preferences():
    channels = {
        "in_app": True,
        "email": True,
        "push": True,
        "sms": False,
        "webhook": False,
        "slack": False,
    }
    return {
        "badge": dict(channels),
        "comment": dict(channels),
        "achievement": dict(channels),
        "lesson_completed": dict(channels),
    }


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("badge", "Badge Earned"),
        ("comment", "New Comment"),
        ("achievement", "Achievement Unlocked"),
        ("lesson_completed", "Lesson Completed"),
    ]

    objects = models.Manager()

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    notif_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)  # type: ignore
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)  # extra payload

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="idx_recipientis_read")
        ]

    def __str__(self):
        return f"[{self.notif_type}] → {self.recipient} | {self.title}"


class NotificationPreference(models.Model):
    objects = models.Manager()

    DIGEST_CHOICES = [
        ("none", "None"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    websocket_enabled = models.BooleanField(default=True)
    digest_frequency = models.CharField(
        max_length=10, choices=DIGEST_CHOICES, default="none"
    )
    digest_time = models.TimeField(default=datetime.time(8, 0))
    channel_preferences = models.JSONField(
        default=default_channel_preferences, blank=True
    )
    webhook_url = models.URLField(max_length=500, blank=True, null=True)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"NotificationPreference(user={self.user_id})"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    def __str__(self):
        return f"PushSubscription(user={self.user.username})"  # type: ignore


class NotificationDelivery(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("bounced", "Bounced"),
        ("opened", "Opened"),
        ("clicked", "Clicked"),
        ("digest_pending", "Waiting for weekly digest"),
        ("batched", "Included in weekly digest"),
        ("cancelled", "Cancelled"),
    ]

    objects = models.Manager()

    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_deliveries"
    )
    channel = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    retry_count = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True)

    # Idempotency key for the event: the same (recipient, channel, dedupe_key) is delivered once.
    dedupe_key = models.CharField(max_length=128, null=True, blank=True)
    # Snapshot of what is delivered, so a retry or crash recovery does not depend on task arguments.
    payload = models.JSONField(default=dict, blank=True)
    digest_batch = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="digest_items",
    )
    # Set while a worker is delivering; another worker may take over once the lease has expired.
    claimed_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    # "transient", "permanent" or "rate_limited" for the last failure; empty while healthy.
    error_class = models.CharField(max_length=20, blank=True)
    # What the provider said about the last attempt.
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "channel"], name="idx_delivery_recipient_chan"
            ),
            models.Index(
                fields=["status", "created_at"], name="idx_delivery_status_created"
            ),
            models.Index(
                fields=["notification", "channel"], name="idx_delivery_notif_chan"
            ),
            models.Index(
                fields=["status", "next_retry_at"], name="idx_delivery_status_retry"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "channel", "dedupe_key"],
                condition=models.Q(dedupe_key__isnull=False),
                name="uniq_delivery_dedupe_key",
            )
        ]

    def __str__(self):
        return (
            f"Delivery #{self.pk} [{self.channel}] -> {self.recipient} ({self.status})"
        )


class NotificationDeadLetter(models.Model):
    objects = models.Manager()

    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dead_letters",
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_dead_letters"
    )
    channel = models.CharField(max_length=50)
    retry_count = models.IntegerField(default=0)
    failed_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-failed_at"]

    def __str__(self):
        return f"DeadLetter [{self.channel}] -> {self.recipient} (Retries: {self.retry_count})"


class NotificationAttempt(models.Model):
    """
    One row per try at delivering a notification: the append-only ledger.

    ``NotificationDelivery`` says where a delivery stands now; this table says how it got there,
    with how long each try took and what the provider answered. Old rows are removed by
    ``purge_notification_ledger`` (see ``apps.notifications.retention``).
    """

    OUTCOME_CHOICES = [
        ("started", "Started"),
        ("sent", "Sent"),
        ("transient_failure", "Transient failure"),
        ("permanent_failure", "Permanent failure"),
        ("rate_limited", "Rate limited"),
        ("skipped", "Skipped (already handled)"),
        ("abandoned", "Abandoned (worker died)"),
    ]

    objects = models.Manager()

    delivery = models.ForeignKey(
        NotificationDelivery, on_delete=models.CASCADE, related_name="attempts"
    )
    attempt_number = models.PositiveIntegerField()
    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default="started"
    )
    error_class = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["delivery_id", "attempt_number", "id"]
        indexes = [
            models.Index(
                fields=["delivery", "attempt_number"], name="idx_attempt_delivery_n"
            ),
            models.Index(fields=["created_at"], name="idx_attempt_created"),
            models.Index(
                fields=["outcome", "started_at"], name="idx_attempt_outcome_started"
            ),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_number} of delivery #{self.delivery_id}: {self.outcome}"
