from apps.organizations.models import Organization
from django.db import models


class Challenge(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    difficulty = models.CharField(max_length=32)
    points = models.PositiveIntegerField(default=50)
    is_featured = models.BooleanField(default=False)
