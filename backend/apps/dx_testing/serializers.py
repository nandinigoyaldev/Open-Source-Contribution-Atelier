from rest_framework import serializers
from apps.dx_testing.models import DXTestRun, DXMetric, DXRecommendation


class DXTestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = DXTestRun
        fields = "__all__"


class DXMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DXMetric
        fields = "__all__"


class DXRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DXRecommendation
        fields = "__all__"
