from rest_framework import serializers
from apps.issue_quality.models import IssueQualityCheck


class IssueQualityCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueQualityCheck
        fields = "__all__"
