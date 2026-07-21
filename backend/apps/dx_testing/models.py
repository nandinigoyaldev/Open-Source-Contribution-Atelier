"""
Models for developer experience testing.
"""

from django.db import models
from django.utils import timezone
import uuid


class DXTestRun(models.Model):
    """
    DX test run record.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Overall metrics
    dx_score = models.FloatField(default=0.0)  # 0-100
    overall_time_seconds = models.FloatField(default=0.0)
    
    # Step metrics
    setup_time_seconds = models.FloatField(default=0.0)
    build_time_seconds = models.FloatField(default=0.0)
    test_time_seconds = models.FloatField(default=0.0)
    pr_time_seconds = models.FloatField(default=0.0)
    
    # Quality metrics
    test_pass_rate = models.FloatField(default=0.0)
    build_success = models.BooleanField(default=False)
    pr_success = models.BooleanField(default=False)
    
    # Friction points
    friction_points = models.JSONField(default=list)
    error_count = models.IntegerField(default=0)
    
    # Recommendations
    recommendations = models.JSONField(default=list)
    
    # Metadata
    environment = models.CharField(max_length=50, default='ci')
    triggered_by = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dx_score']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"DX Test: {self.run_id} - {self.dx_score:.1f}"


class DXMetric(models.Model):
    """
    Aggregated DX metrics.
    """

    date = models.DateField(unique=True, db_index=True)
    
    # Average scores
    avg_dx_score = models.FloatField(default=0.0)
    avg_setup_time = models.FloatField(default=0.0)
    avg_build_time = models.FloatField(default=0.0)
    avg_test_time = models.FloatField(default=0.0)
    avg_pr_time = models.FloatField(default=0.0)
    
    # Success rates
    build_success_rate = models.FloatField(default=0.0)
    test_success_rate = models.FloatField(default=0.0)
    pr_success_rate = models.FloatField(default=0.0)
    
    # Friction tracking
    common_friction_points = models.JSONField(default=list)
    total_errors = models.IntegerField(default=0)
    
    # Trends
    dx_trend = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"DX Metrics: {self.date}"


class DXRecommendation(models.Model):
    """
    Actionable DX recommendations.
    """

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    category = models.CharField(max_length=50)  # setup, build, test, pr, docs
    
    # Metrics
    impact_score = models.FloatField(default=0.0)  # 0-100
    effort_score = models.FloatField(default=0.0)  # 0-100
    
    # Status
    is_implemented = models.BooleanField(default=False)
    implemented_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-impact_score']
    
    def __str__(self):
        return f"{self.title} - {self.priority}"