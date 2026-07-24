from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from apps.issues.models import Issue
from apps.dashboard.models import PullRequest
from django.contrib.auth import get_user_model

User = get_user_model()

class ProductivityService:
    def get_contributor_metrics(self, days=30):
        """Aggregate contributor metrics."""
        cutoff = timezone.now() - timedelta(days=days)
        
        users = User.objects.filter(is_active=True)
        metrics = []
        
        for user in users:
            # PR metrics
            prs = PullRequest.objects.filter(author=user, created_at__gte=cutoff)
            prs_closed = prs.filter(closed_at__isnull=False)
            
            # Issue metrics
            issues = Issue.objects.filter(assigned_to=user, created_at__gte=cutoff)
            issues_closed = issues.filter(closed_at__isnull=False)
            
            # Average review time
            avg_review_time = prs_closed.aggregate(
                avg=Avg('closed_at' - 'created_at')
            )['avg']
            
            # Stalled PRs
            stalled = prs.filter(updated_at__lte=timezone.now() - timedelta(days=7))
            
            metrics.append({
                'username': user.username,
                'prs_opened': prs.count(),
                'prs_closed': prs_closed.count(),
                'issues_assigned': issues.count(),
                'issues_closed': issues_closed.count(),
                'avg_review_time': avg_review_time.total_seconds() / 3600 if avg_review_time else 0,
                'stalled_prs': stalled.count(),
                'pr_merge_rate': round((prs_closed.count() / prs.count()) * 100, 1) if prs.count() > 0 else 0
            })
        
        return sorted(metrics, key=lambda x: x['prs_closed'], reverse=True)

    def get_stalled_prs(self):
        """Get PRs with no activity in 7+ days."""
        cutoff = timezone.now() - timedelta(days=7)
        return PullRequest.objects.filter(
            updated_at__lte=cutoff,
            closed_at__isnull=True
        ).select_related('author', 'repository')

    def get_review_bottlenecks(self):
        """Find PRs waiting >3 days for review."""
        cutoff = timezone.now() - timedelta(days=3)
        return PullRequest.objects.filter(
            created_at__lte=cutoff,
            closed_at__isnull=True,
            reviews__isnull=True
        ).select_related('author', 'repository')