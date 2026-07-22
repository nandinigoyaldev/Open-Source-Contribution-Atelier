from rest_framework import serializers
from apps.ml_triage.models import (
    Issue,
    Comment,
    Reaction,
    TrainingData,
    IssuePrediction,
)


class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = "__all__"


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"


class ReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = "__all__"


class TrainingDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingData
        fields = "__all__"


class IssuePredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssuePrediction
        fields = "__all__"
