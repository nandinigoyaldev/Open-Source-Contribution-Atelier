from rest_framework import permissions, serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CodeSnapshot
from .serializers import CodeSnapshotSerializer
from .services import verify_git_command


class SandboxVerifySerializer(serializers.Serializer):
    command = serializers.CharField()
    expected_command = serializers.CharField()


class SandboxVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SandboxVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = verify_git_command(
            serializer.validated_data["command"],
            serializer.validated_data["expected_command"],
        )
        return Response(
            {
                "accepted": result.accepted,
                "feedback": result.feedback,
                "score_delta": result.score_delta,
            },
            status=status.HTTP_200_OK,
        )


class CodeSnapshotViewSet(viewsets.ModelViewSet):
    serializer_class = CodeSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CodeSnapshot.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


from .models import Project, ProjectFile
from .serializers import ProjectSerializer, ProjectFileSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProjectFileViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectFileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProjectFile.objects.filter(project__user=self.request.user)


from .models import CodeExecutionTrace
from .serializers import CodeExecutionTraceSerializer

class CodeExecutionTraceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CodeExecutionTraceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CodeExecutionTrace.objects.filter(user=self.request.user)


from .models import CodeReviewThread
from .serializers import CodeReviewThreadSerializer

class CodeReviewThreadViewSet(viewsets.ModelViewSet):
    serializer_class = CodeReviewThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CodeReviewThread.objects.prefetch_related('comments', 'comments__user').all()
        session_id = self.request.query_params.get('session', None)
        if session_id is not None:
            queryset = queryset.filter(session_id=session_id)
        return queryset


from .models import SnippetCollection, CodeSnippet
from .serializers import SnippetCollectionSerializer, CodeSnippetSerializer

class SnippetCollectionViewSet(viewsets.ModelViewSet):
    serializer_class = SnippetCollectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SnippetCollection.objects.filter(user=self.request.user)


class CodeSnippetViewSet(viewsets.ModelViewSet):
    serializer_class = CodeSnippetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CodeSnippet.objects.filter(user=self.request.user)
        
        # Filtering
        collection_id = self.request.query_params.get('collection', None)
        if collection_id is not None:
            queryset = queryset.filter(collection_id=collection_id)
            
        is_favorite = self.request.query_params.get('is_favorite', None)
        if is_favorite is not None:
            queryset = queryset.filter(is_favorite=is_favorite.lower() == 'true')
            
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(title__icontains=search)
            
        return queryset

from .models import TerminalSession, TerminalCommand
from .serializers import TerminalSessionSerializer, TerminalCommandSerializer

class TerminalSessionViewSet(viewsets.ModelViewSet):
    serializer_class = TerminalSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TerminalSession.objects.filter(user=self.request.user)

class TerminalCommandViewSet(viewsets.ModelViewSet):
    serializer_class = TerminalCommandSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TerminalCommand.objects.filter(session__user=self.request.user)

    def perform_create(self, serializer):
        command = serializer.validated_data.get('command', '')
        # Mocking execution for now
        output = f"Executed: {command}\n"
        
        import time
        start = time.time()
        
        # Simple mock logic
        if command.startswith('echo '):
            output = command[5:] + "\n"
        elif command.strip() == 'clear':
            output = ""
            
        execution_time = (time.time() - start) * 1000
        serializer.save(output=output, execution_time=execution_time)
