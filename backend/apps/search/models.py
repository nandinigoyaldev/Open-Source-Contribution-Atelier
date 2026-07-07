from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class SearchDocument(models.Model):
    """
    A unified model to store searchable text from all entities across the application.
    Enables highly performant Postgres Full-Text Search and Trigram similarity queries
    without needing a heavy external search engine.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    title = models.CharField(max_length=255)
    body_text = models.TextField()

    # Store the pre-computed tsvector
    search_vector = SearchVectorField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Fast full-text lookups
        indexes = [
            GinIndex(fields=["search_vector"], name="search_vector_gin_idx"),
            GinIndex(
                fields=["title"],
                name="trigram_title_gin_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ]
        # Prevent duplicate index entries for the same object
        unique_together = ("content_type", "object_id")

    def __str__(self):
        return f"SearchDoc: {self.title} ({self.content_type.name})"


class SearchAnalytics(models.Model):
    query = models.CharField(max_length=500, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    result_count = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name_plural = "search analytics"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["query", "created_at"]),
        ]

    def __str__(self):
        return f"Search: {self.query} ({self.result_count} results)"
