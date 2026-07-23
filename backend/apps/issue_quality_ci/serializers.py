from rest_framework import serializers
from .models import IssueQualityRecord, QualityMetric, QualityComment, QualityTrend


class IssueQualityRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueQualityRecord
        fields = "__all__"


class QualityMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityMetric
        fields = "__all__"


class QualityCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityComment
        fields = "__all__"


class QualityTrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityTrend
        fields = "__all__"
