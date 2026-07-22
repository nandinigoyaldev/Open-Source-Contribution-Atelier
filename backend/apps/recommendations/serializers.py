from rest_framework import serializers

from .models import Recommendation, OSSIssue


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = (
            "id",
            "content_type",
            "content_id",
            "title",
            "reason",
            "priority_score",
            "is_dismissed",
            "created_at",
        )


class OSSIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = OSSIssue
        fields = "__all__"
