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


from .models import SnapshotFile, WorkspaceSnapshot


class SnapshotFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SnapshotFile
        fields = ["id", "snapshot", "path", "content", "language"]
        read_only_fields = ["id"]


class WorkspaceSnapshotSerializer(serializers.ModelSerializer):
    files = SnapshotFileSerializer(many=True, read_only=True)

    class Meta:
        model = WorkspaceSnapshot
        fields = [
            "id",
            "project",
            "name",
            "description",
            "metadata",
            "is_public",
            "files",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


from .models import MaintainerScenario, MaintainerEvaluation

class MaintainerScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintainerScenario
        fields = ['id', 'title', 'description', 'original_code', 'flawed_code', 'diff_content', 'required_findings', 'created_at']
        read_only_fields = ['id', 'created_at']

class MaintainerEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintainerEvaluation
        fields = ['id', 'scenario', 'user', 'submitted_comments', 'score', 'passed', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


from .models import CollabSession, CollabSessionLog

class CollabSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollabSession
        fields = ["id", "project", "allowed_users", "created_at", "is_active"]
        read_only_fields = ["id", "created_at"]

from .models import PipelineExecution, PipelineJob, ConflictScenario, ConflictAttempt


class PipelineJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineJob
        fields = [
            "id",
            "job_type",
            "status",
            "log_output",
            "duration_seconds",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "created_at", "completed_at"]


class PipelineExecutionSerializer(serializers.ModelSerializer):
    jobs = PipelineJobSerializer(many=True, read_only=True)

    class Meta:
        model = PipelineExecution
        fields = [
            "id",
            "project",
            "trigger_command",
            "status",
            "jobs",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "status", "created_at", "completed_at"]


class ConflictScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConflictScenario
        fields = [
            "id",
            "title",
            "description",
            "language",
            "difficulty",
            "base_code",
            "current_code",
            "incoming_code",
            "hint",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ConflictAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConflictAttempt
        fields = [
            "id",
            "scenario",
            "user",
            "submitted_code",
            "passed",
            "error_message",
            "created_at",
        ]
        read_only_fields = ["id", "user", "passed", "error_message", "created_at"]

