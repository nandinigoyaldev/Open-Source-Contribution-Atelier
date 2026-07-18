from rest_framework import viewsets, permissions, serializers
from .models import A11yIssue
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count

class A11yIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = A11yIssue
        fields = '__all__'

class A11yIssueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows accessibility issues to be viewed by admins.
    """
    queryset = A11yIssue.objects.all()
    serializer_class = A11yIssueSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        stats = A11yIssue.objects.values('severity', 'status').annotate(count=Count('id'))
        
        return Response({
            "stats": list(stats)
        })
