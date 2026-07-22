from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import IssueQualityRecord, QualityMetric, QualityComment, QualityTrend
from .serializers import (
    IssueQualityRecordSerializer,
    QualityMetricSerializer,
    QualityCommentSerializer,
    QualityTrendSerializer,
)


class IssueQualityRecordViewSet(viewsets.ModelViewSet):
    queryset = IssueQualityRecord.objects.all()
    serializer_class = IssueQualityRecordSerializer
    permission_classes = [IsAuthenticated]


class QualityMetricViewSet(viewsets.ModelViewSet):
    queryset = QualityMetric.objects.all()
    serializer_class = QualityMetricSerializer
    permission_classes = [IsAuthenticated]


class QualityCommentViewSet(viewsets.ModelViewSet):
    queryset = QualityComment.objects.all()
    serializer_class = QualityCommentSerializer
    permission_classes = [IsAuthenticated]


class QualityTrendViewSet(viewsets.ModelViewSet):
    queryset = QualityTrend.objects.all()
    serializer_class = QualityTrendSerializer
    permission_classes = [IsAuthenticated]
