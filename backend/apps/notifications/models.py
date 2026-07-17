from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("badge", "Badge Earned"),
        ("comment", "New Comment"),
        ("achievement", "Achievement Unlocked"),
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
    notif_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
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
    """Backward-compatible global notification toggles."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    websocket_enabled = models.BooleanField(default=True)


class NotificationDelivery(models.Model):
    """Unified delivery log (one row per notification x channel)."""

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_BOUNCED = "bounced"
    STATUS_OPENED = "opened"
    STATUS_CLICKED = "clicked"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_BOUNCED, "Bounced"),
        (STATUS_OPENED, "Opened"),
        (STATUS_CLICKED, "Clicked"),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    notification = models.ForeignKey(
        "Notification",
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    channel_id = models.CharField(max_length=50)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["recipient", "channel_id", "status"],
                name="idx_delivery_rl",
            ),
            models.Index(
                fields=["notification", "channel_id"],
                name="idx_delivery_notif_chan",
            ),
        ]

    def __str__(self):
        return (
            f"Delivery({self.id}) {self.notification_id} → {self.recipient_id} "
            f"[{self.channel_id}:{self.status}]"
        )


class NotificationDeadLetter(models.Model):
    """Permanent failures after all retries are exhausted."""

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_dead_letters",
    )
    notification = models.ForeignKey(
        "Notification",
        on_delete=models.CASCADE,
        related_name="dead_letters",
    )
    channel_id = models.CharField(max_length=50)

    error = models.TextField()
    payload_snapshot = models.JSONField(default=dict, blank=True)

    failed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "channel_id"], name="idx_dead_letter"),
        ]

    def __str__(self):
        return (
            f"DeadLetter({self.id}) {self.notification_id} → {self.recipient_id} "
            f"[{self.channel_id}]"
        )


class NotificationChannelPreference(models.Model):
    """Per notification type/channel opt-in/out."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notif_type = models.CharField(max_length=20)
    channel_id = models.CharField(max_length=50)
    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "notif_type", "channel_id")
        indexes = [
            models.Index(
                fields=["user", "notif_type", "channel_id"],
                name="idx_notif_chan_pref",
            )
        ]

    def __str__(self):
        return (
            f"Pref(user={self.user_id}, {self.notif_type}:{self.channel_id}="
            f"{self.enabled})"
        )


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

