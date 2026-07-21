"""
Views for DX testing.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Avg
from apps.dx_testing.models import DXTestRun, DXMetric, DXRecommendation
from apps.dx_testing.serializers import DXTestRunSerializer, DXRecommendationSerializer
import logging

logger = logging.getLogger(__name__)


class DXTestRunViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DX test runs.
    """
    queryset = DXTestRun.objects.all()
    serializer_class = DXTestRunSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def report(self, request):
        """
        Report DX test results.
        """
        data = request.data
        
        # Calculate DX score
        steps = data.get('steps', [])
        total_duration = data.get('totalDuration', 0)
        errors = data.get('errors', 0)
        
        success_rate = 1 - (errors / len(steps)) if steps else 0
        
        # Calculate average step time
        avg_time = sum(s.get('duration', 0) for s in steps) / len(steps) if steps else 0
        
        # Calculate DX score
        success_score = success_rate * 70
        speed_score = max(0, min(30, 30 - (avg_time / 1000)))
        dx_score = success_score + speed_score
        
        # Identify friction points
        friction_points = []
        for step in steps:
            if not step.get('success', False):
                friction_points.append({
                    'step': step.get('name', ''),
                    'error': step.get('error', 'Unknown error'),
                })
            elif step.get('duration', 0) > 5000:  # >5 seconds is slow
                friction_points.append({
                    'step': step.get('name', ''),
                    'warning': f"Slow step: {step.get('duration')}ms",
                })
        
        # Generate recommendations
        recommendations = self._generate_recommendations(friction_points)
        
        # Create test run
        test_run = DXTestRun.objects.create(
            run_id=data.get('runId', f"dx_{time.time()}"),
            status='completed',
            dx_score=dx_score,
            overall_time_seconds=total_duration / 1000,
            error_count=errors,
            friction_points=friction_points,
            recommendations=recommendations,
            completed_at=timezone.now()
        )
        
        return Response({
            'id': test_run.id,
            'dx_score': dx_score,
            'friction_points': friction_points,
            'recommendations': recommendations,
        })

    def _generate_recommendations(self, friction_points: list) -> list:
        """
        Generate recommendations from friction points.
        """
        recommendations = []
        
        for point in friction_points:
            step = point.get('step', '')
            if 'fork' in step.lower():
                recommendations.append({
                    'title': 'Simplify fork workflow',
                    'description': 'Add a "Fork with one click" button to reduce friction',
                    'priority': 'medium',
                })
            elif 'setup' in step.lower() or 'install' in step.lower():
                recommendations.append({
                    'title': 'Improve setup documentation',
                    'description': 'Add a setup script that automates environment configuration',
                    'priority': 'high',
                })
            elif 'test' in step.lower():
                recommendations.append({
                    'title': 'Speed up test execution',
                    'description': 'Implement parallel test execution to reduce wait times',
                    'priority': 'medium',
                })
            elif 'pr' in step.lower():
                recommendations.append({
                    'title': 'Streamline PR workflow',
                    'description': 'Add PR templates and automated checks to speed up review',
                    'priority': 'high',
                })
        
        return recommendations