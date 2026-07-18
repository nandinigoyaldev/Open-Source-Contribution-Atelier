from django.db import models
from django.contrib.auth import get_user_model

User= get_user_model()

class Experiment(models.Model):
    """A/B test experiment"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    variants = models.JSONField(default=list)  # ['control', 'variant_a', 'variant_b']
    traffic_allocation = models.FloatField(default=1.0)  # 0.0 - 1.0
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class ExperimentAssignment(models.Model):
    """User to variant mapping."""
    
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    variant = models.CharField(max_length=50)
    assigned_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['experiment', 'user']

class ExperimentEvent(models.Model):
    """Analytics event for experiments."""
    
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    variant = models.CharField(max_length=50)
    event_type = models.CharField(max_length=50)  # 'view', 'click', 'conversion'
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)