"""
Models for hierarchical issue organization and categorization.
"""

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
import uuid
import json
from mptt.models import MPTTModel, TreeForeignKey


class Category(MPTTModel):
    """
    Hierarchical category tree for issues.

    Example:
    Project
    ├── Backend
    │   ├── API
    │   │   ├── Authentication
    │   │   └── Rate Limiting
    │   └── Database
    │       ├── Migrations
    │       └── Queries
    ├── Frontend
    │   ├── UI Components
    │   ├── State Management
    │   └── Styling
    └── DevOps
        ├── CI/CD
        └── Deployment
    """

    CATEGORY_TYPES = [
        ("project", "Project"),
        ("component", "Component"),
        ("sub_component", "Sub-Component"),
        ("feature", "Feature"),
        ("module", "Module"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    category_type = models.CharField(
        max_length=20, choices=CATEGORY_TYPES, default="component"
    )

    # MPTT fields for hierarchy
    parent = TreeForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )

    # Metadata
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True)
    order = models.IntegerField(default=0)

    # Statistics
    issue_count = models.IntegerField(default=0)
    open_issue_count = models.IntegerField(default=0)
    closed_issue_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ["order", "name"]

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_full_path(self):
        """Get full hierarchical path."""
        ancestors = self.get_ancestors(include_self=True)
        return " → ".join([a.name for a in ancestors])

    def get_level_display(self):
        """Get human-readable level display."""
        level_map = {
            0: "Project",
            1: "Component",
            2: "Sub-Component",
            3: "Feature",
            4: "Module",
        }
        return level_map.get(self.level, "Category")


class IssueCategoryAssignment(models.Model):
    """
    Assign categories to issues.
    """

    ASSIGNMENT_TYPES = [
        ("manual", "Manual"),
        ("auto", "Auto-tagged"),
        ("suggested", "Suggested"),
    ]

    issue_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="category_assignments"
    )
    issue_object_id = models.PositiveIntegerField()
    issue = GenericForeignKey("issue_content_type", "issue_object_id")

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="issue_assignments"
    )

    assignment_type = models.CharField(
        max_length=20, choices=ASSIGNMENT_TYPES, default="auto"
    )
    confidence_score = models.FloatField(
        default=0.0, help_text="Confidence score for auto-assignment"
    )

    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["issue_content_type", "issue_object_id", "category"]]

    def __str__(self):
        return f"{self.issue} → {self.category}"


class IssueTag(models.Model):
    """
    Tags for issues with ML-based auto-tagging.
    """

    TAG_TYPES = [
        ("skill", "Skill"),
        ("technology", "Technology"),
        ("domain", "Domain"),
        ("difficulty", "Difficulty"),
        ("area", "Area"),
        ("custom", "Custom"),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    tag_type = models.CharField(max_length=20, choices=TAG_TYPES, default="custom")

    # Metadata
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, blank=True)

    # Usage stats
    usage_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IssueTagAssignment(models.Model):
    """
    Assign tags to issues.
    """

    issue_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="tag_assignments"
    )
    issue_object_id = models.PositiveIntegerField()
    issue = GenericForeignKey("issue_content_type", "issue_object_id")

    tag = models.ForeignKey(
        IssueTag, on_delete=models.CASCADE, related_name="issue_assignments"
    )

    # Auto-tagging metadata
    auto_tagged = models.BooleanField(default=False)
    confidence_score = models.FloatField(default=0.0)

    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["issue_content_type", "issue_object_id", "tag"]]

    def __str__(self):
        return f"{self.issue} → {self.tag}"


class CategorySuggestion(models.Model):
    """
    ML-based category suggestions for issues.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    issue_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="category_suggestions"
    )
    issue_object_id = models.PositiveIntegerField()
    issue = GenericForeignKey("issue_content_type", "issue_object_id")

    suggested_categories = models.JSONField(
        default=list, help_text="List of suggested category IDs with scores"
    )
    suggested_tags = models.JSONField(
        default=list, help_text="List of suggested tag IDs with scores"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # ML metadata
    model_version = models.CharField(max_length=50, default="1.0")
    confidence_scores = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Suggestion for {self.issue}"

    def approve(self):
        """Approve suggestions and create assignments."""
        self.status = "approved"
        self.save()

        # Create category assignments
        for cat_data in self.suggested_categories:
            if cat_data.get("score", 0) > 0.5:
                IssueCategoryAssignment.objects.get_or_create(
                    issue_content_type=self.issue_content_type,
                    issue_object_id=self.issue_object_id,
                    category_id=cat_data["id"],
                    defaults={
                        "assignment_type": "suggested",
                        "confidence_score": cat_data["score"],
                    },
                )

        # Create tag assignments
        for tag_data in self.suggested_tags:
            if tag_data.get("score", 0) > 0.5:
                IssueTagAssignment.objects.get_or_create(
                    issue_content_type=self.issue_content_type,
                    issue_object_id=self.issue_object_id,
                    tag_id=tag_data["id"],
                    defaults={
                        "auto_tagged": True,
                        "confidence_score": tag_data["score"],
                    },
                )
