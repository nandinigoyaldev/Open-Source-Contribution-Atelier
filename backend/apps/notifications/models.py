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
    DIGEST_CHOICES = [
        ("none", "None"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    websocket_enabled = models.BooleanField(default=True)
    digest_frequency = models.CharField(max_length=10, choices=DIGEST_CHOICES, default="none")
    digest_time = models.TimeField(default=datetime.time(8, 0))
    channel_preferences = models.JSONField(default=default_channel_preferences, blank=True)
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "channel"], name="idx_delivery_recipient_chan"),
            models.Index(fields=["status", "created_at"], name="idx_delivery_status_created"),
            models.Index(fields=["notification", "channel"], name="idx_delivery_notif_chan"),
        ]

    def __str__(self):
        return f"Delivery #{self.id} [{self.channel}] -> {self.recipient} ({self.status})"


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

