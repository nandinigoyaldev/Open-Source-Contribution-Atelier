from django.contrib.auth.models import User
from django.db import models

class Recommendation(models.Model):
    objects = models.Manager()
    
    class ContentType(models.TextChoices):
        LESSON = "lesson", "Lesson"
        CHALLENGE = "challenge", "Challenge"
        QUIZ = "quiz", "Quiz"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recommendations")
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    content_id = models.CharField(max_length=255) # Assuming slug or id
    title = models.CharField(max_length=255, default="")
    reason = models.TextField()
    priority_score = models.IntegerField(default=0)
    is_dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority_score", "-created_at"]
        unique_together = ("user", "content_type", "content_id")

    def __str__(self):
        return f"{self.user.username} - {self.content_type} {self.title} ({self.priority_score})"
