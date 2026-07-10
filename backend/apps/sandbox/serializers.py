from rest_framework import serializers

from .models import (
    CodeReviewComment,
    CodeReviewThread,
    CodeSnapshot,
    CodeSnippet,
    Project,
    ProjectFile,
    SnippetCollection,
)


class CodeSnapshotSerializer(serializers.ModelSerializer):
    is_auto = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = CodeSnapshot
        fields = ["id", "user", "code", "timestamp", "label", "is_auto"]
        read_only_fields = ["id", "user", "timestamp"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = [
            "id",
            "project",
            "path",
            "content",
            "language",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectSerializer(serializers.ModelSerializer):
    files = ProjectFileSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ["id", "user", "name", "files", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


from .models import CodeExecutionTrace


class CodeExecutionTraceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeExecutionTrace
        fields = ["id", "user", "code", "trace_events", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


from django.contrib.auth import get_user_model

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class CodeReviewCommentSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = CodeReviewComment
        fields = ["id", "thread", "user", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class CodeReviewThreadSerializer(serializers.ModelSerializer):
    comments = CodeReviewCommentSerializer(many=True, read_only=True)

    class Meta:
        model = CodeReviewThread
        fields = [
            "id",
            "session",
            "line_number",
            "is_resolved",
            "comments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SnippetCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SnippetCollection
        fields = ["id", "user", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class CodeSnippetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeSnippet
        fields = [
            "id",
            "user",
            "collection",
            "title",
            "description",
            "code",
            "language",
            "is_favorite",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
