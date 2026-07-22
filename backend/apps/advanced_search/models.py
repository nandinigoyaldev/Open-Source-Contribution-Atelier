from django.contrib.auth import get_user_model

User = get_user_model()
"""
Models for advanced search with relevance scoring and semantic understanding.
"""

from django.db import models
from django.conf import settings

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.utils import timezone
import uuid
import json


class SearchEmbedding(models.Model):
    """
    Store embeddings for semantic search.
    """

    content_type = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField()

    # Embedding vector (stored as JSON list)
    embedding = models.JSONField(help_text="Vector embedding for semantic search")
    model_version = models.CharField(max_length=50, default="1.0")

    # Metadata
    text_preview = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["content_type", "object_id"]]
        indexes = [
            models.Index(fields=["content_type"], name="idx_content_type"),
        ]

    def __str__(self):
        return f"Embedding for {self.content_type}:{self.object_id}"


class UserSearchProfile(models.Model):
    """
    User search preferences and history for personalization.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="search_profile",
    )

    # Search history
    search_history = models.JSONField(default=list, help_text="List of recent searches")
    clicked_results = models.JSONField(
        default=list, help_text="List of clicked result IDs"
    )

    # User interests (inferred from search behavior)
    inferred_interests = models.JSONField(
        default=list, help_text="Inferred interests from search behavior"
    )

    # Skill vector (from search behavior)
    skill_vector = models.JSONField(
        default=dict, help_text="Skill-based vector for personalization"
    )

    # Search preferences
    preferred_categories = models.JSONField(
        default=list, help_text="Preferred content categories"
    )
    preferred_difficulty = models.CharField(
        max_length=20, blank=True, help_text="Preferred difficulty level"
    )

    # Analytics
    total_searches = models.IntegerField(default=0)
    average_click_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Search profile for {self.user.username}"

    def add_search_query(self, query: str, results: list, clicked: list = None):
        """
        Add a search query to history.
        """
        # Add to history
        self.search_history.append(
            {
                "query": query,
                "timestamp": timezone.now().isoformat(),
                "results_count": len(results),
                "clicked": clicked or [],
            }
        )

        # Keep only last 100 searches
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]

        self.total_searches += 1

        # Update interests
        self._update_interests(query, results)

        self.save()

    def _update_interests(self, query: str, results: list):
        """
        Update user interests based on search behavior.
        """
        # Extract keywords from query
        keywords = query.lower().split()

        # Extract categories from results
        categories = []
        for result in results:
            if "category" in result:
                categories.append(result["category"])

        # Update interests
        current_interests = set(self.inferred_interests)

        # Add new interests from query
        for keyword in keywords:
            if len(keyword) > 3 and keyword not in stopwords:
                current_interests.add(keyword)

        # Add categories
        for category in categories:
            if category:
                current_interests.add(category)

        self.inferred_interests = list(current_interests)[:20]

    def record_click(self, result_id: str):
        """
        Record a click on a search result.
        """
        if result_id not in self.clicked_results:
            self.clicked_results.append(result_id)

        # Update click rate
        total = len(self.clicked_results)
        self.average_click_rate = total / (self.total_searches + 1)

        self.save()


class SearchAnalytics(models.Model):
    """
    Search analytics for improving relevance.
    """

    date = models.DateField(unique=True, db_index=True)

    # Search metrics
    total_searches = models.IntegerField(default=0)
    unique_searchers = models.IntegerField(default=0)
    zero_result_searches = models.IntegerField(default=0)

    # Click metrics
    total_clicks = models.IntegerField(default=0)
    click_through_rate = models.FloatField(default=0.0)
    average_position = models.FloatField(default=0.0)

    # Query analysis
    top_queries = models.JSONField(default=list)
    top_categories = models.JSONField(default=list)
    popular_keywords = models.JSONField(default=list)

    # Performance
    avg_response_time = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Search Analytics - {self.date}"
