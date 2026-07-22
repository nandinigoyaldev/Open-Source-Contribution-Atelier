from rest_framework import serializers
from .models import (
    ContributorProfile,
    SkillTag,
    IssueSkillTag,
    NewcomerFriendlinessScore,
    Recommendation,
    SkillGapAnalysis,
)


class ContributorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributorProfile
        fields = "__all__"


class SkillTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillTag
        fields = "__all__"


class IssueSkillTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueSkillTag
        fields = "__all__"


class NewcomerFriendlinessScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewcomerFriendlinessScore
        fields = "__all__"


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = "__all__"


class SkillGapAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillGapAnalysis
        fields = "__all__"
