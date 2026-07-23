from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Suggestion(models.Model):
    """Inline code suggestion."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    review = models.ForeignKey('CodeReviewThread', on_delete=models.CASCADE, related_name='suggestions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=500)
    line_start = models.IntegerField()
    line_end = models.IntegerField()
    original_code = models.TextField()
    suggested_code = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ReviewSession(models.Model):
    """Real-time review session."""
    
    id = models.CharField(max_length=100, primary_key=True)
    participants = models.ManyToManyField(User)
    file_path = models.CharField(max_length=500)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)