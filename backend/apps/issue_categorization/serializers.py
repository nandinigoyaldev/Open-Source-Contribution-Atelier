from rest_framework import serializers
from .models import (
    Category,
    IssueCategoryAssignment,
    IssueTag,
    IssueTagAssignment,
    CategorySuggestion,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class IssueCategoryAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueCategoryAssignment
        fields = "__all__"


class IssueTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueTag
        fields = "__all__"


class IssueTagAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueTagAssignment
        fields = "__all__"


class CategorySuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorySuggestion
        fields = "__all__"
