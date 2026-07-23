from rest_framework import serializers
from .models import PRReview, CodeIssue, PRReviewComment, ReviewConfig


class PRReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PRReview
        fields = "__all__"


class CodeIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeIssue
        fields = "__all__"


class PRReviewCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PRReviewComment
        fields = "__all__"


class ReviewConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewConfig
        fields = "__all__"
