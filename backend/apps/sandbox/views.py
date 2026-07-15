"""
Views for sandbox app with duplicate execution prevention and all features.
"""

from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
import logging

from .models import CodeSnapshot, Project, ProjectFile, CodeExecutionTrace, CodeReviewThread, SnippetCollection, CodeSnippet
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

from rest_framework.throttling import ScopedRateThrottle

class SandboxVerifySerializer(serializers.Serializer):
    command = serializers.CharField()
    expected_command = serializers.CharField()
    # Optional fields for duplicate prevention
    code = serializers.CharField(required=False, default='')
    payload = serializers.JSONField(required=False, default={})


class SandboxVerifyView(APIView):
    """
    Sandbox verification with duplicate execution prevention.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sandbox_user"

    @prevent_duplicate_execution(
        get_user_id=lambda request: request.user.id,
        get_code=lambda request: request.data.get('code', ''),
        get_payload=lambda request: request.data.get('payload', {})
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
                serializer.validated_data.get('code', ''),
                serializer.validated_data.get('payload', {})
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
        collection_id = self.request.query_params.get('collection', None)
        if collection_id is not None:
            queryset = queryset.filter(collection_id=collection_id)
        
        # Filtering by favorite
        is_favorite = self.request.query_params.get('is_favorite', None)
        if is_favorite is not None:
            queryset = queryset.filter(is_favorite=is_favorite.lower() == 'true')
        
        # Search by title
        search = self.request.query_params.get('search', None)
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
        code = request.query_params.get('code', '')
        payload_raw = request.query_params.get('payload', '{}')
        
        if not code:
            return Response(
                {'error': 'Code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            import json
            payload = json.loads(payload_raw)
        except:
            payload = {}
        
        is_duplicate = ExecutionTracker.is_duplicate(
            request.user.id,
            code,
            payload
        )
        
        return Response({
            'is_duplicate': is_duplicate,
            'user_id': request.user.id,
        })


# ============================================================
# EXECUTION TRACKER ADMIN (For testing)
# ============================================================

class ClearExecutionView(APIView):
    """
    Clear execution from cache (for testing/admin).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '')
        payload = request.data.get('payload', {})
        
        if not code:
            return Response(
                {'error': 'Code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ExecutionTracker.clear_execution(
            request.user.id,
            code,
            payload
        )
        
        return Response(
            {'message': 'Execution cleared from cache'},
            status=status.HTTP_200_OK
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
    
    @action(detail=True, methods=["post"])
    def invite_mentor(self, request, pk=None):
        session = self.get_object()
        
        # Only project owner can invite
        if session.project and session.project.user != request.user:
            return Response({"error": "Only the project owner can invite mentors."}, status=403)
            
        username = request.data.get("username")
        User = get_user_model()
        try:
            mentor = User.objects.get(username=username)
            session.allowed_users.add(mentor)
            return Response({"status": "invited", "mentor": username})
        except User.DoesNotExist:
            return Response({"error": "Mentor not found"}, status=404)
