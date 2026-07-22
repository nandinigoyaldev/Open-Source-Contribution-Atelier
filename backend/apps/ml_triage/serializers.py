from rest_framework import serializers
from apps.ml_triage.models import Issue


class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = "__all__"


class TrainingDataSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False)
    priority = serializers.CharField(required=False)
