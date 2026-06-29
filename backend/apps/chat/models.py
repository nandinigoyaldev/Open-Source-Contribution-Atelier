from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Message(models.Model):
    room_id = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()  # type: ignore

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.room_id}] {self.user.username}: {self.content[:20]}"
