from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("badge", "Badge Earned"),
        ("comment", "New Comment"),
    ]

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
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)  # extra payload

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"[{self.notif_type}] → {self.recipient} | {self.title}"
