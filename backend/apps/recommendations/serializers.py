from rest_framework import serializers
from .models import Recommendation

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
