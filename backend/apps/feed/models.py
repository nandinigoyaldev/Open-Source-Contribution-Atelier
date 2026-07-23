from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class FeedEvent(models.Model):
    event_type = models.CharField(max_length=50, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=255, blank=True)
    target_title = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
