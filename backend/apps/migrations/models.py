from django.db import models

class MigrationPlan(models.Model):
    """Track migration deployment phases."""
    
    PHASE_CHOICES = [
        ('phase1', 'Phase 1 - Safe Changes'),
        ('phase2', 'Phase 2 - Data Backfill'),
        ('phase3', 'Phase 3 - Cleanup'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]
    
    migration_name = models.CharField(max_length=255)
    phase = models.CharField(max_length=10, choices=PHASE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    rollback_plan = models.JSONField(default=dict)
    pre_migration_snapshot = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-started_at']