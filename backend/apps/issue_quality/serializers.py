from rest_framework import serializers
from apps.issue_quality.models import IssueQualityCheck, DuplicateIssue, WontfixPattern


class IssueQualityCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueQualityCheck
        fields = "__all__"


class DuplicateIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = DuplicateIssue
        fields = "__all__"


class WontfixPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = WontfixPattern
        fields = "__all__"
