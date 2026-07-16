"""
ML models for issue triage and priority scoring.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Issue(models.Model):
    """
    GitHub issue metadata for ML training.
    """
    
    CATEGORY_CHOICES = [
        ('bug', 'Bug'),
        ('feature', 'Feature Request'),
        ('documentation', 'Documentation'),
        ('question', 'Question'),
        ('other', 'Other'),
    ]
    
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    # GitHub metadata
    github_id = models.IntegerField(unique=True)
    repository = models.CharField(max_length=255)
    number = models.IntegerField()
    title = models.TextField()
    body = models.TextField(blank=True)
    state = models.CharField(max_length=20, default='open')
    
    # User associations
    author = models.CharField(max_length=255)
    assignees = models.JSONField(default=list)
    
    # Timestamps
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # ML-predicted fields
    predicted_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, null=True, blank=True)
    predicted_priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, null=True, blank=True)
    
    # ML scores
    priority_score = models.FloatField(default=0.0)
    hotness_score = models.FloatField(default=0.0)
    lifetime_prediction_days = models.FloatField(null=True, blank=True)
    
    # Feature vectors (for model training)
    feature_vector = models.JSONField(null=True, blank=True)
    model_version = models.CharField(max_length=50, default='1.0')
    
    # Analytics
    comments_count = models.IntegerField(default=0)
    reactions_count = models.IntegerField(default=0)
    label_count = models.IntegerField(default=0)
    
    # Confidence
    confidence_score = models.FloatField(default=0.0)
    
    created_at_local = models.DateTimeField(auto_now_add=True)
    updated_at_local = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority_score']
        indexes = [
            models.Index(fields=['repository', 'state']),
            models.Index(fields=['priority_score']),
            models.Index(fields=['predicted_category']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Issue #{self.number}: {self.title[:50]}"
    
    def calculate_hotness(self):
        """
        Calculate hotness score based on recent activity.
        Similar to YouTube trending algorithm.
        """
        import math
        from datetime import timedelta
        
        # Age in days
        age_days = (timezone.now() - self.created_at).days + 1
        
        # Recent activity factor
        recent_comments = Comment.objects.filter(issue=self, created_at__gte=timezone.now() - timedelta(days=7)).count()
        recent_reactions = Reaction.objects.filter(issue=self, created_at__gte=timezone.now() - timedelta(days=7)).count()
        
        # Hotness formula: (comments + reactions) / (age_days ^ 1.5) * 100
        activity = recent_comments * 2 + recent_reactions
        self.hotness_score = (activity / math.pow(age_days, 1.5)) * 100
        self.save(update_fields=['hotness_score'])
        return self.hotness_score


class Comment(models.Model):
    """Issue comments for training."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField()
    
    def __str__(self):
        return f"Comment on Issue #{self.issue.number}"


class Reaction(models.Model):
    """Issue reactions (thumbs up, heart, etc.)"""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='reactions')
    user = models.CharField(max_length=255)
    reaction_type = models.CharField(max_length=50)
    created_at = models.DateTimeField()
    
    def __str__(self):
        return f"{self.reaction_type} on Issue #{self.issue.number}"


class TrainingData(models.Model):
    """Training data for ML models."""
    version = models.CharField(max_length=50)
    trained_at = models.DateTimeField(auto_now_add=True)
    accuracy = models.FloatField()
    precision = models.FloatField()
    recall = models.FloatField()
    f1_score = models.FloatField()
    model_file = models.CharField(max_length=500)
    feature_names = models.JSONField(default=list)
    total_samples = models.IntegerField()
    
    class Meta:
        ordering = ['-trained_at']
    
    def __str__(self):
        return f"Training v{self.version} - {self.accuracy:.2f}%"


class IssuePrediction(models.Model):
    """Stored predictions for issues."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='predictions')
    predicted_at = models.DateTimeField(auto_now_add=True)
    category = models.CharField(max_length=50)
    priority = models.CharField(max_length=20)
    confidence = models.FloatField()
    lifetime_days = models.FloatField()
    model_version = models.CharField(max_length=50)
    
    class Meta:
        ordering = ['-predicted_at']
    
    def __str__(self):
        return f"Prediction for Issue #{self.issue.number}"