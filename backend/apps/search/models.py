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
    description = models.TextField(blank=True, default="")
    tags = models.CharField(max_length=500, blank=True, default="")
    body_text = models.TextField()

    # Denormalized content type name for fast filtering without a JOIN
    content_type_name = models.CharField(max_length=100, blank=True, default="")

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
            GinIndex(
                fields=["description"],
                name="trigram_desc_gin_idx",
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
            models.Index(fields=["query", "created_at"], name="idx_querycreated_at"),
        ]

    def __str__(self):
        return f"Search: {self.query} ({self.result_count} results)"


class SearchIndexFailure(models.Model):
    """
    Dead-letter record for a Meilisearch write that kept failing.

    One open row per (document_id, operation); repeated failures update it.
    No document text is stored: replay reads the current SearchDocument.
    """

    OP_INDEX = "index"
    OP_DELETE = "delete"
    OPERATION_CHOICES = [(OP_INDEX, "Index"), (OP_DELETE, "Delete")]

    document_id = models.CharField(max_length=64)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)
    attempts = models.PositiveIntegerField()
    last_error = models.CharField(max_length=500, blank=True, default="")
    first_failed_at = models.DateTimeField()
    last_failed_at = models.DateTimeField()

    class Meta:
        ordering = ["first_failed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document_id", "operation"],
                name="uniq_search_failure_doc_operation",
            )
        ]

    def __str__(self):
        return f"{self.operation} {self.document_id} ({self.attempts} attempts)"
