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
        fields = [
            "id",
            "title",
            "description",
            "original_code",
            "flawed_code",
            "diff_content",
            "required_findings",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MaintainerEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintainerEvaluation
        fields = [
            "id",
            "scenario",
            "user",
            "submitted_comments",
            "score",
            "passed",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
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

    def validate_trigger_command(self, value):
        if not value:
            return value
        from .services.pipeline_simulator import validate_trigger_command

        is_valid, sanitized_or_reason = validate_trigger_command(value)
        if not is_valid:
            raise serializers.ValidationError(sanitized_or_reason)
        return sanitized_or_reason


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


# ============================================================
# FEATURE 2: TOXIC COMMUNITY DE-ESCALATION TRAINER
# ============================================================

from .models import ModerationScenario, DialogueNode, DialogueChoice, ModerationAttempt


class DialogueChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DialogueChoice
        fields = ["id", "to_node_id", "text", "is_moderation_action"]


class DialogueNodeSerializer(serializers.ModelSerializer):
    choices = DialogueChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = DialogueNode
        fields = ["id", "node_id", "text", "is_endpoint", "is_successful", "choices"]


class ModerationScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationScenario
        fields = ["id", "title", "description", "initial_tension", "created_at"]


class ModerationAttemptSerializer(serializers.ModelSerializer):
    scenario = ModerationScenarioSerializer(read_only=True)
    current_node = DialogueNodeSerializer(read_only=True)

    class Meta:
        model = ModerationAttempt
        fields = [
            "id",
            "user",
            "scenario",
            "current_node",
            "current_tension",
            "is_completed",
            "is_successful",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


# ============================================================
# FEATURE 3: LICENSE & DEPENDENCY DETECTIVE
# ============================================================

from .models import LicenseScenario, DependencyDiff, LicenseAttempt


class DependencyDiffSerializer(serializers.ModelSerializer):
    class Meta:
        model = DependencyDiff
        fields = ["id", "package_name", "package_license", "diff_text"]


class LicenseScenarioSerializer(serializers.ModelSerializer):
    dependencies = DependencyDiffSerializer(many=True, read_only=True)

    class Meta:
        model = LicenseScenario
        fields = [
            "id",
            "title",
            "description",
            "base_project_license",
            "difficulty",
            "created_at",
            "dependencies",
        ]


class LicenseAttemptSerializer(serializers.ModelSerializer):
    scenario = LicenseScenarioSerializer(read_only=True)

    class Meta:
        model = LicenseAttempt
        fields = [
            "id",
            "user",
            "scenario",
            "approved",
            "is_successful",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "user", "is_successful", "feedback", "created_at"]


# ============================================================
# FEATURE 11: ISSUE TRIAGE & LABELING MAINTAINER SCENARIO
# ============================================================

from .models import TriageIssue, TriageAttempt


class TriageIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = TriageIssue
        fields = [
            "id",
            "title",
            "raw_issue_title",
            "raw_issue_body",
            "correct_labels",
            "hint",
            "difficulty",
            "created_at",
        ]
        read_only_fields = ["id", "correct_labels", "created_at"]


class TriageAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = TriageAttempt
        fields = [
            "id",
            "issue",
            "user",
            "submitted_labels",
            "submitted_response",
            "label_score",
            "response_score",
            "total_score",
            "passed",
            "feedback",
            "badge_awarded",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "label_score",
            "response_score",
            "total_score",
            "passed",
            "feedback",
            "badge_awarded",
            "created_at",
        ]


# ============================================================
# FEATURE: ADR Sandbox Simulator
# ============================================================

from .models import ADRScenario, ADROption, ADRAttempt


class ADROptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ADROption
        fields = ["id", "title", "pros", "cons"]


class ADRScenarioSerializer(serializers.ModelSerializer):
    options = ADROptionSerializer(many=True, read_only=True)

    class Meta:
        model = ADRScenario
        fields = ["id", "title", "context", "constraints", "created_at", "options"]


class ADRAttemptSerializer(serializers.ModelSerializer):
    scenario = ADRScenarioSerializer(read_only=True)

    class Meta:
        model = ADRAttempt
        fields = [
            "id",
            "user",
            "scenario",
            "selected_option",
            "is_successful",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "user", "is_successful", "feedback", "created_at"]
