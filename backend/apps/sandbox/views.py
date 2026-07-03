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
