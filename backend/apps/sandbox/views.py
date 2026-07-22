"""
Views for sandbox app with duplicate execution prevention and all features.
"""

from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
import logging

from .models import (
    CodeSnapshot,
    Project,
    ProjectFile,
    CodeExecutionTrace,
    CodeReviewThread,
    SnippetCollection,
    CodeSnippet,
)
from .serializers import (
    CodeSnapshotSerializer,
    ProjectSerializer,
    ProjectFileSerializer,
    CodeExecutionTraceSerializer,
    CodeReviewThreadSerializer,
    SnippetCollectionSerializer,
    CodeSnippetSerializer,
)
from .services import verify_git_command
from .services.execution_tracker import ExecutionTracker, prevent_duplicate_execution

logger = logging.getLogger(__name__)


# ============================================================
# SANDOX VERIFY WITH DUPLICATE PREVENTION
# ============================================================

from apps.core.throttling import SlidingWindowScopedThrottle


class SandboxVerifySerializer(serializers.Serializer):
    command = serializers.CharField()
    expected_command = serializers.CharField()
    # Optional fields for duplicate prevention
    code = serializers.CharField(required=False, default="")
    payload = serializers.JSONField(required=False, default={})


class SandboxVerifyView(APIView):
    """
    Sandbox verification with duplicate execution prevention.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [SlidingWindowScopedThrottle]
    throttle_scope = "sandbox_user"

    @prevent_duplicate_execution(
        get_user_id=lambda request: request.user.id,
        get_code=lambda request: request.data.get("code", ""),
        get_payload=lambda request: request.data.get("payload", {}),
    )
    def post(self, request):
        serializer = SandboxVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = verify_git_command(
            serializer.validated_data["command"],
            serializer.validated_data["expected_command"],
        )

        # If verification succeeded, mark execution as used
        if result.accepted:
            ExecutionTracker.mark_execution_used(
                request.user.id,
                serializer.validated_data.get("code", ""),
                serializer.validated_data.get("payload", {}),
            )

        return Response(
            {
                "accepted": result.accepted,
                "feedback": result.feedback,
                "score_delta": result.score_delta,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# CODE SNAPSHOTS
# ============================================================


class CodeSnapshotViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CodeSnapshot model.
    """

    serializer_class = CodeSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CodeSnapshot.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ============================================================
# PROJECTS
# ============================================================

from .models import Project, ProjectFile
from .serializers import ProjectFileSerializer, ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Project model.
    """

    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def replace(self, request, pk=None):
        project = self.get_object()
        query = request.data.get("query")
        replacement = request.data.get("replacement")
        is_regex = request.data.get("is_regex", False)
        match_case = request.data.get("match_case", False)

        if not query:
            return Response({"error": "Query is required"}, status=400)

        import re

        flags = 0 if match_case else re.IGNORECASE
        try:
            pattern = re.compile(query if is_regex else re.escape(query), flags)
        except re.error:
            return Response({"error": "Invalid regular expression"}, status=400)

        files = ProjectFile.objects.filter(project=project)
        previous_state = {}
        updated_files = []

        from django.db import transaction

        from .models import BulkReplaceOperation

        with transaction.atomic():
            for f in files:
                if pattern.search(f.content):
                    previous_state[str(f.id)] = f.content
                    f.content = pattern.sub(replacement, f.content)
                    updated_files.append(f)

            if previous_state:
                BulkReplaceOperation.objects.create(
                    project=project, user=request.user, previous_state=previous_state
                )
                ProjectFile.objects.bulk_update(updated_files, ["content"])

        return Response({"modified_count": len(updated_files)})

    @action(detail=True, methods=["post"])
    def undo_replace(self, request, pk=None):
        project = self.get_object()
        from .models import BulkReplaceOperation

        operation = (
            BulkReplaceOperation.objects.filter(project=project, user=request.user)
            .order_by("-created_at")
            .first()
        )

        if not operation:
            return Response({"error": "No recent operation to undo"}, status=400)

        from django.db import transaction

        with transaction.atomic():
            files_to_update = []
            for file_id, content in operation.previous_state.items():
                f = ProjectFile.objects.filter(id=file_id).first()
                if f:
                    f.content = content
                    files_to_update.append(f)

            if files_to_update:
                ProjectFile.objects.bulk_update(files_to_update, ["content"])
            operation.delete()

        return Response({"restored_count": len(files_to_update)})

    @action(detail=True, methods=["get"])
    def export_zip(self, request, pk=None):
        """Export project workspace as a ZIP file."""
        import io
        import zipfile
        from django.http import HttpResponse

        project = self.get_object()
        files = ProjectFile.objects.filter(project=project)

        import os

        # Create ZIP in memory
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file in files:
                # Sanitize path to prevent Zip Slip (Directory Traversal)
                raw_path = (file.path or "").replace("\\", "/").lstrip("/")
                clean_path = os.path.normpath(raw_path).replace("\\", "/")
                if (
                    clean_path in ("", ".", "..")
                    or clean_path.startswith("../")
                    or ":" in clean_path.split("/", 1)[0]
                ):
                    continue  # Skip paths that could escape the archive root
                zip_file.writestr(clean_path, file.content)

            # Add a README file
            readme_content = f"""# {project.name}

This workspace was exported from Open Source Contribution Atelier.

Project: {project.name}
Exported at: {project.updated_at}
Total files: {files.count()}

## Files
"""
            for file in files:
                readme_content += f"- {file.path}\n"
            zip_file.writestr("README.md", readme_content)

        # Prepare response
        buffer.seek(0)
        filename = f"{project.name.replace(' ', '_')}-export.zip"
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ProjectFileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ProjectFile model.
    """

    serializer_class = ProjectFileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProjectFile.objects.filter(project__user=self.request.user)


# ============================================================
# CODE EXECUTION TRACE
# ============================================================


class CodeExecutionTraceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for CodeExecutionTrace model (read-only).
    """

    serializer_class = CodeExecutionTraceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CodeExecutionTrace.objects.filter(user=self.request.user)


# ============================================================
# CODE REVIEW THREADS
# ============================================================


class CodeReviewThreadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CodeReviewThread model.
    """

    serializer_class = CodeReviewThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CodeReviewThread.objects.prefetch_related(
            "comments", "comments__user"
        ).all()
        session_id = self.request.query_params.get("session", None)
        if session_id is not None:
            queryset = queryset.filter(session_id=session_id)
        return queryset


# ============================================================
# SNIPPET COLLECTIONS
# ============================================================

from .models import CodeSnippet, SnippetCollection
from .serializers import CodeSnippetSerializer, SnippetCollectionSerializer


class SnippetCollectionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SnippetCollection model.
    """

    serializer_class = SnippetCollectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SnippetCollection.objects.filter(user=self.request.user)


class CodeSnippetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CodeSnippet model with filtering.
    """

    serializer_class = CodeSnippetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CodeSnippet.objects.filter(user=self.request.user)

        # Filtering by collection
        collection_id = self.request.query_params.get("collection", None)
        if collection_id is not None:
            queryset = queryset.filter(collection_id=collection_id)

        # Filtering by favorite
        is_favorite = self.request.query_params.get("is_favorite", None)
        if is_favorite is not None:
            queryset = queryset.filter(is_favorite=is_favorite.lower() == "true")

        # Search by title
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(title__icontains=search)

        return queryset


# ============================================================
# EXECUTION STATUS (For debugging)
# ============================================================


class ExecutionStatusView(APIView):
    """
    Check execution status for debugging duplicate prevention.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("code", "")
        payload_raw = request.query_params.get("payload", "{}")

        if not code:
            return Response(
                {"error": "Code is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            import json

            payload = json.loads(payload_raw)
        except:
            payload = {}

        is_duplicate = ExecutionTracker.is_duplicate(request.user.id, code, payload)

        return Response(
            {
                "is_duplicate": is_duplicate,
                "user_id": request.user.id,
            }
        )


# ============================================================
# EXECUTION TRACKER ADMIN (For testing)
# ============================================================


class ClearExecutionView(APIView):
    """
    Clear execution from cache (for testing/admin).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "")
        payload = request.data.get("payload", {})

        if not code:
            return Response(
                {"error": "Code is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        ExecutionTracker.clear_execution(request.user.id, code, payload)

        return Response(
            {"message": "Execution cleared from cache"}, status=status.HTTP_200_OK
        )

        # Filtering
        collection_id = self.request.query_params.get("collection", None)
        if collection_id is not None:
            queryset = queryset.filter(collection_id=collection_id)

        is_favorite = self.request.query_params.get("is_favorite", None)
        if is_favorite is not None:
            queryset = queryset.filter(is_favorite=is_favorite.lower() == "true")

        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(title__icontains=search)

        return queryset


from django.db.models import Q

from .models import WorkspaceSnapshot
from .serializers import WorkspaceSnapshotSerializer


class WorkspaceSnapshotViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # A user can see snapshots of their own projects, plus any snapshot
        # marked is_public (matching the field's documented purpose: "whether
        # this snapshot can be forked by anyone").
        return WorkspaceSnapshot.objects.filter(
            Q(project__user=self.request.user) | Q(is_public=True)
        ).select_related("project")

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        if project is not None and project.user_id != self.request.user.id:
            raise serializers.ValidationError(
                {"project": "You do not own this project."}
            )
        serializer.save()


# ============================================================
# MAINTAINER ROLEPLAY
# ============================================================

from .models import MaintainerScenario, MaintainerEvaluation
from .serializers import MaintainerScenarioSerializer, MaintainerEvaluationSerializer


class MaintainerScenarioViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MaintainerScenarioSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = MaintainerScenario.objects.all()


class MaintainerEvaluationViewSet(viewsets.ModelViewSet):
    serializer_class = MaintainerEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MaintainerEvaluation.objects.filter(user=self.request.user)


from .models import CollabSession
from .serializers import CollabSessionSerializer
from django.contrib.auth import get_user_model


class CollabSessionViewSet(viewsets.ModelViewSet):
    serializer_class = CollabSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CollabSession.objects.filter(
            Q(project__user=self.request.user) | Q(allowed_users=self.request.user)
        ).distinct()

    def destroy(self, request, *args, **kwargs):
        session = self.get_object()
        if session.project and session.project.user != request.user:
            return Response({"error": "Only the host can end the session."}, status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        try:
            session = CollabSession.objects.get(pk=pk, is_active=True)
            if request.user not in session.allowed_users.all() and (
                not session.project or session.project.user != request.user
            ):
                session.allowed_users.add(request.user)
            return Response(
                CollabSessionSerializer(session, context={"request": request}).data
            )
        except CollabSession.DoesNotExist:
            return Response({"error": "Active session not found"}, status=404)

    @action(detail=True, methods=["post"])
    def invite_mentor(self, request, pk=None):
        session = self.get_object()

        # Only project owner can invite
        if session.project and session.project.user != request.user:
            return Response(
                {"error": "Only the project owner can invite mentors."}, status=403
            )

        username = request.data.get("username")
        User = get_user_model()
        try:
            mentor = User.objects.get(username=username)
            session.allowed_users.add(mentor)
            return Response({"status": "invited", "mentor": username})
        except User.DoesNotExist:
            return Response({"error": "Mentor not found"}, status=404)


# ============================================================
# CI/CD PIPELINE SIMULATOR
# ============================================================

from .models import PipelineExecution, PipelineJob
from .serializers import PipelineExecutionSerializer


class PipelineExecutionViewSet(viewsets.ModelViewSet):
    serializer_class = PipelineExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PipelineExecution.objects.filter(
            user=self.request.user
        ).prefetch_related("jobs")

    def perform_create(self, serializer):
        from .services.pipeline_simulator import run_pipeline_simulation

        pipeline = serializer.save(user=self.request.user)

        code = ""
        if pipeline.project:
            first_file = pipeline.project.files.first()
            if first_file:
                code = first_file.content

        run_pipeline_simulation(pipeline, code=code)


# ============================================================
# MERGE CONFLICT ARENA
# ============================================================

from .models import ConflictScenario, ConflictAttempt
from .serializers import ConflictScenarioSerializer, ConflictAttemptSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
import re


class ConflictScenarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ConflictScenario.objects.all()
    serializer_class = ConflictScenarioSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def resolve_conflict(self, request, pk=None):
        scenario = self.get_object()
        submitted_code = request.data.get("submitted_code", "")

        if (
            re.search(r"<<<<<<<\s*HEAD", submitted_code)
            or re.search(r"=======", submitted_code)
            or re.search(r">>>>>>>", submitted_code)
        ):
            error_msg = "Your code still contains unresolved Git conflict markers."
            ConflictAttempt.objects.create(
                scenario=scenario,
                user=request.user,
                submitted_code=submitted_code,
                passed=False,
                error_message=error_msg,
            )
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        def _normalize(text):
            return "\n".join(line.rstrip() for line in text.splitlines()).strip()

        passed = _normalize(submitted_code) == _normalize(scenario.expected_resolution)
        error_msg = (
            ""
            if passed
            else "The resolved code does not match the expected correct output."
        )

        attempt = ConflictAttempt.objects.create(
            scenario=scenario,
            user=request.user,
            submitted_code=submitted_code,
            passed=passed,
            error_message=error_msg,
        )

        return Response(
            {
                "passed": passed,
                "message": "Conflict resolved successfully!" if passed else error_msg,
            },
            status=status.HTTP_200_OK if passed else status.HTTP_400_BAD_REQUEST,
        )


# ============================================================
# FEATURE 2: TOXIC COMMUNITY DE-ESCALATION TRAINER
# ============================================================

from .models import ModerationScenario, DialogueNode, DialogueChoice, ModerationAttempt
from .serializers import (
    ModerationScenarioSerializer,
    ModerationAttemptSerializer,
    DialogueNodeSerializer,
)


class ModerationScenarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ModerationScenario.objects.all().order_by("-created_at")
    serializer_class = ModerationScenarioSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        scenario = self.get_object()
        user = request.user if request.user.is_authenticated else None
        start_node = scenario.nodes.first()

        attempt = ModerationAttempt.objects.create(
            user=user,
            scenario=scenario,
            current_node=start_node,
            current_tension=scenario.initial_tension,
        )

        return Response(
            {
                "attempt_id": attempt.id,
                "node": DialogueNodeSerializer(start_node).data,
                "current_tension": attempt.current_tension,
            }
        )

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        scenario = self.get_object()
        choice_id = request.data.get("choice_id")
        attempt_id = request.data.get("attempt_id")

        try:
            attempt = ModerationAttempt.objects.get(id=attempt_id, scenario=scenario)
            choice = DialogueChoice.objects.get(
                id=choice_id, from_node=attempt.current_node
            )
        except (ModerationAttempt.DoesNotExist, DialogueChoice.DoesNotExist):
            return Response(
                {"error": "Invalid choice or attempt."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if attempt.is_completed:
            return Response(
                {"error": "Attempt is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attempt.current_tension += choice.tension_delta
        attempt.current_tension = max(0, min(100, attempt.current_tension))

        try:
            next_node = DialogueNode.objects.get(
                scenario=scenario, node_id=choice.to_node_id
            )
        except DialogueNode.DoesNotExist:
            return Response(
                {"error": "Next node not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        attempt.current_node = next_node

        if next_node.is_endpoint:
            attempt.is_completed = True
            attempt.is_successful = next_node.is_successful

        attempt.save()

        return Response(
            {
                "node": DialogueNodeSerializer(next_node).data,
                "current_tension": attempt.current_tension,
                "is_completed": attempt.is_completed,
                "is_successful": attempt.is_successful,
            }
        )


# ============================================================
# FEATURE 3: LICENSE & DEPENDENCY DETECTIVE
# ============================================================

from .models import LicenseScenario, DependencyDiff, LicenseAttempt
from .serializers import LicenseScenarioSerializer, LicenseAttemptSerializer


class LicenseScenarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for License Scenarios (Dependency Detective).
    """

    queryset = (
        LicenseScenario.objects.all()
        .prefetch_related("dependencies")
        .order_by("-created_at")
    )
    serializer_class = LicenseScenarioSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["post"])
    def evaluate(self, request, pk=None):
        scenario = self.get_object()
        user = request.user if request.user.is_authenticated else None
        approved = request.data.get("approved")
        flagged_dependencies = request.data.get("flagged_dependencies", [])

        if approved is None:
            return Response(
                {"error": "You must provide 'approved' boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        violations = scenario.dependencies.filter(is_violation=True)
        has_violations = violations.exists()

        is_successful = False
        feedback = ""

        if has_violations and approved:
            is_successful = False
            feedback = "You approved a PR with a license violation!"
        elif has_violations and not approved:
            violation_ids = set(violations.values_list("id", flat=True))
            flagged_set = set(flagged_dependencies)

            if violation_ids == flagged_set:
                is_successful = True
                feedback = "Great job! You caught all the license violations."
            elif violation_ids.issubset(flagged_set):
                is_successful = False
                feedback = (
                    "You caught the violations, but you also flagged safe dependencies."
                )
            else:
                is_successful = False
                feedback = "You rejected the PR, but you missed some of the actual license violations."
        elif not has_violations and approved:
            is_successful = True
            feedback = "Correct! The PR is safe to merge."
        elif not has_violations and not approved:
            is_successful = False
            feedback = "You rejected a perfectly safe PR."

        LicenseAttempt.objects.create(
            user=user,
            scenario=scenario,
            approved=approved,
            is_successful=is_successful,
            feedback=feedback,
        )

        return Response({"is_successful": is_successful, "feedback": feedback})


# ============================================================
# FEATURE 11: ISSUE TRIAGE & LABELING MAINTAINER SCENARIO
# ============================================================

from .models import TriageIssue, TriageAttempt
from .serializers import TriageIssueSerializer, TriageAttemptSerializer


def _score_triage(issue: TriageIssue, submitted_labels: list, submitted_response: str):
    correct_set = {lbl.lower() for lbl in (issue.correct_labels or [])}
    submitted_set = {lbl.lower() for lbl in (submitted_labels or [])}
    if correct_set or submitted_set:
        intersection = correct_set & submitted_set
        union = correct_set | submitted_set
        jaccard = len(intersection) / len(union)
    else:
        jaccard = 0.0
    label_score = round(jaccard * 50)

    body = submitted_response.lower()

    politeness_keywords = [
        "thank",
        "appreciate",
        "welcome",
        "glad",
        "happy to help",
        "great report",
        "hope",
        "sorry",
        "apologies",
    ]
    action_keywords = [
        "could you",
        "please",
        "can you",
        "would you",
        "let us know",
        "share",
        "provide",
        "attach",
        "include",
    ]
    missing_info_keywords = [
        "steps",
        "environment",
        "version",
        "reproduce",
        "repro",
        "os",
        "operating system",
        "browser",
        "output",
        "expected",
        "actual",
        "error",
        "stack trace",
        "log",
    ]

    polite_hits = sum(1 for kw in politeness_keywords if kw in body)
    action_hits = sum(1 for kw in action_keywords if kw in body)
    missing_hits = sum(1 for kw in missing_info_keywords if kw in body)

    politeness_score = min(polite_hits * 7, 20)
    action_score = min(action_hits * 5, 20)
    missing_score = min(missing_hits * 3, 10)
    response_score = politeness_score + action_score + missing_score

    feedback_lines = []
    correct_not_submitted = correct_set - submitted_set
    submitted_not_correct = submitted_set - correct_set
    if correct_not_submitted:
        feedback_lines.append(
            f"You missed the following correct labels: {', '.join(sorted(correct_not_submitted))}."
        )
    if submitted_not_correct:
        feedback_lines.append(
            f"The following labels were incorrect: {', '.join(sorted(submitted_not_correct))}."
        )
    if polite_hits == 0:
        feedback_lines.append("Your response could be more polite and welcoming.")
    if action_hits == 0:
        feedback_lines.append(
            "Your response should ask the reporter for more information."
        )
    if missing_hits == 0:
        feedback_lines.append(
            "Your response should mention what specific information is missing (e.g., steps to reproduce, environment)."
        )
    if not feedback_lines:
        feedback_lines.append(
            "Excellent triage! Your labels and response are both accurate and professional."
        )

    total_score = label_score + response_score
    passed = total_score >= 70
    badge = "triager" if passed else ""

    return (
        label_score,
        response_score,
        total_score,
        passed,
        " ".join(feedback_lines),
        badge,
    )


class TriageIssueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TriageIssue.objects.all()
    serializer_class = TriageIssueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        difficulty = self.request.query_params.get("difficulty")
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        return qs

    @action(detail=True, methods=["post"])
    def submit_triage(self, request, pk=None):
        issue = self.get_object()
        submitted_labels = request.data.get("submitted_labels", [])
        submitted_response = request.data.get("submitted_response", "").strip()

        if not isinstance(submitted_labels, list):
            return Response(
                {"error": "submitted_labels must be a list of strings."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invalid_labels = [
            lbl
            for lbl in submitted_labels
            if lbl.lower() not in [v.lower() for v in TriageIssue.VALID_LABELS]
        ]
        if invalid_labels:
            return Response(
                {
                    "error": f"Invalid labels: {invalid_labels}. Allowed: {TriageIssue.VALID_LABELS}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not submitted_response:
            return Response(
                {"error": "submitted_response cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        label_score, response_score, total_score, passed, feedback, badge = (
            _score_triage(issue, submitted_labels, submitted_response)
        )

        attempt = TriageAttempt.objects.create(
            issue=issue,
            user=request.user,
            submitted_labels=submitted_labels,
            submitted_response=submitted_response,
            label_score=label_score,
            response_score=response_score,
            total_score=total_score,
            passed=passed,
            feedback=feedback,
            badge_awarded=badge,
        )

        return Response(
            TriageAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def my_attempts(self, request):
        attempts = TriageAttempt.objects.filter(user=request.user).select_related(
            "issue"
        )
        return Response(TriageAttemptSerializer(attempts, many=True).data)
