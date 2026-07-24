from django.db import models


class Plugin(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    version = models.CharField(max_length=50)
    api_version = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    author = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)
    manifest = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name} ({self.version})"
