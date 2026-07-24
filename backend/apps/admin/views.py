from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from .services import ProductivityService
from .serializers import ProductivitySerializer
import csv
from django.http import HttpResponse

class ProductivityDashboardView(APIView):
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        service = ProductivityService()
        days = request.query_params.get('days', 30)
        
        data = {
            'metrics': service.get_contributor_metrics(int(days)),
            'stalled_prs': service.get_stalled_prs(),
            'review_bottlenecks': service.get_review_bottlenecks(),
            'total_active': self._get_active_count(),
            'daily_trend': self._get_daily_trend()
        }
        
        return Response(data)
    
    def _get_active_count(self):
        cutoff = timezone.now() - timedelta(days=1)
        return User.objects.filter(
            Q(pullrequest__created_at__gte=cutoff) |
            Q(issue__updated_at__gte=cutoff)
        ).distinct().count()
    
    def _get_daily_trend(self):
        # Daily PR opened/closed trend
        from django.db.models import Count
        from datetime import timedelta
        import calendar
        
        days = 30
        cutoff = timezone.now() - timedelta(days=days)
        trend = []
        
        for i in range(days):
            day = cutoff + timedelta(days=i)
            next_day = day + timedelta(days=1)
            
            opened = PullRequest.objects.filter(
                created_at__gte=day,
                created_at__lt=next_day
            ).count()
            
            closed = PullRequest.objects.filter(
                closed_at__gte=day,
                closed_at__lt=next_day
            ).count()
            
            trend.append({
                'date': day.strftime('%Y-%m-%d'),
                'opened': opened,
                'closed': closed
            })
        
        return trend

    def export_csv(self, request):
        """Export metrics as CSV."""
        service = ProductivityService()
        metrics = service.get_contributor_metrics()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="productivity.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Username', 'PRs Opened', 'PRs Closed', 'Issues Assigned', 'Issues Closed', 'Avg Review Time (h)', 'Stalled PRs', 'Merge Rate %'])
        
        for m in metrics:
            writer.writerow([
                m['username'],
                m['prs_opened'],
                m['prs_closed'],
                m['issues_assigned'],
                m['issues_closed'],
                round(m['avg_review_time'], 1),
                m['stalled_prs'],
                m['pr_merge_rate']
            ])
        
        return response