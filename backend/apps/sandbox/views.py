"""
Views for sandbox app with duplicate execution prevention and all features.
"""

from rest_framework import permissions, serializers, status, viewsets
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
        queryset = CodeReviewThread.objects.prefetch_related('comments', 'comments__user').all()
        session_id = self.request.query_params.get('session', None)
        if session_id is not None:
            queryset = queryset.filter(session_id=session_id)
        return queryset


# ============================================================
# SNIPPET COLLECTIONS
# ============================================================

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