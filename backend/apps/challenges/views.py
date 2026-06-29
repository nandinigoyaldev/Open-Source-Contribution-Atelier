import json

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Challenge
from .serializers import ChallengeSerializer
from .throttles import SandboxAnonRateThrottle, SandboxUserRateThrottle


class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    """Existing view — untouched."""

    serializer_class = ChallengeSerializer

    def get_queryset(self):
        return Challenge.objects.filter(organization=self.request.user.organization)


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
                {"detail": "No code provided."}, status=status.HTTP_400_BAD_REQUEST
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


class BulkChallengeUploadView(APIView):
    """
    POST /api/challenges/bulk-upload/
    Accepts a JSON file upload to bulk create Challenge records.
    Restricted to Staff/Admin users only.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "No file uploaded. Please provide a valid JSON file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = json.load(file_obj)
            if not isinstance(data, list):
                return Response(
                    {
                        "error": "Invalid format: The JSON file must contain a list of objects."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                challenges_to_create = []
                for item in data:
                    challenges_to_create.append(
                        Challenge(
                            organization=request.user.organization,
                            title=item.get("title"),
                            slug=item.get("slug"),
                            summary=item.get("summary", ""),
                            difficulty=item.get("difficulty", "beginner"),
                            points=item.get("points", 50),
                            is_featured=item.get("is_featured", False),
                        )
                    )
                Challenge.objects.bulk_create(challenges_to_create)

            return Response(
                {
                    "message": f"Successfully created {len(challenges_to_create)} challenges."
                },
                status=status.HTTP_201_CREATED,
            )

        except json.JSONDecodeError:
            return Response(
                {
                    "error": "Failed to parse JSON. Please ensure the file is valid JSON."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
