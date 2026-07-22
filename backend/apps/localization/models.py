from django.db import models


class LocalizedContent(models.Model):
    key = models.CharField(max_length=255)
    language_code = models.CharField(max_length=10)
    translation = models.TextField()

    class Meta:
        unique_together = ("key", "language_code")

    def __str__(self):
        return f"{self.key} ({self.language_code})"
