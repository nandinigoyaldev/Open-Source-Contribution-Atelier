from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

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
