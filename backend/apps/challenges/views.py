from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Challenge
from .serializers import ChallengeSerializer
from .throttles import SandboxAnonRateThrottle, SandboxUserRateThrottle


class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    """Existing view — untouched."""

    serializer_class = ChallengeSerializer

    def get_queryset(self):
        return Challenge.objects.filter(
            organization=self.request.user.organization
        )


class SandboxExecutionView(APIView):
    """
    POST /api/challenges/sandbox/execute/

    Executes user-submitted code in the sandbox.
    Rate limited to 10 requests/minute for both anonymous and authenticated users.
    Returns HTTP 429 when limit is exceeded.
    """

    # Scoped throttles — ONLY this view is rate limited
    throttle_classes = [SandboxAnonRateThrottle, SandboxUserRateThrottle]

    # Allow both anonymous and authenticated users
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Expected body: { "code": "...", "language": "python" }
        Wire this to your actual sandbox execution logic.
        """

        code = request.data.get("code", "")
        language = request.data.get("language", "python")

        if not code:
            return Response(
                {"detail": "No code provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: replace with actual sandbox execution call
        # result = execute_code(code=code, language=language)
        # return Response(result, status=status.HTTP_200_OK)

        return Response(
            {
                "detail": "Sandbox execution triggered.",
                "language": language,
            },
            status=status.HTTP_200_OK,
        )