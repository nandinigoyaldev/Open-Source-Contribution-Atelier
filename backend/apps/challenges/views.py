import json
import logging
import subprocess
import sys
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Challenge
from .serializers import ChallengeSerializer
from .throttles import SandboxAnonRateThrottle, SandboxUserRateThrottle
from .verifiers import get_supported_languages, get_verifier

from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    """Existing view — untouched."""

    serializer_class = ChallengeSerializer

    def get_queryset(self):
        return Challenge.objects.filter(organization=self.request.user.organization)


class SandboxExecutionView(APIView):
    """
    POST /api/challenges/sandbox/execute/

    Executes user-submitted code in the sandbox using the appropriate language verifier.
    Rate limited to 10 requests/minute for both anonymous and authenticated users.
    Returns HTTP 429 when limit is exceeded.
    """

    throttle_classes = [SandboxAnonRateThrottle, SandboxUserRateThrottle]
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        code = request.data.get("code", "")
        language = request.data.get("language", "python")
        expected = request.data.get("expected", None)

        if not code:
            return Response(
                {"detail": "No code provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        verifier = get_verifier(language)
        if verifier is None:
            return Response(
                {
                    "detail": f"Unsupported language: '{language}'.",
                    "supported_languages": get_supported_languages(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = verifier.verify(code, expected=expected)

        return Response(
            {
                "accepted": result.accepted,
                "feedback": result.feedback,
                "score_delta": result.score_delta,
                "language": language,
            },
            status=status.HTTP_200_OK,
        )


class SandboxRunView(APIView):
    """
    POST /api/challenges/sandbox/run/

    Actually executes code and returns real program output.
    Python: runs via subprocess with timeout.
    Rust: compiles and runs via the Rust Playground API.
    JavaScript: runs in-browser via eval (frontend-only).
    """

    permission_classes = [AllowAny]

    RUST_PLAYGROUND_URL = "https://play.rust-lang.org/execute"
    REQUEST_TIMEOUT = 20
    PYTHON_TIMEOUT = 10

    def post(self, request, *args, **kwargs):
        code = request.data.get("code", "")
        language = request.data.get("language", "")

        if not code:
            return Response(
                {"detail": "No code provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        if language == "python":
            return self._run_python(code)
        elif language == "rust":
            return self._run_rust(code)

        return Response(
            {"detail": f"Execution not supported for language: '{language}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _run_python(self, code: str):
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=self.PYTHON_TIMEOUT,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            return Response(
                {
                    "output": "Execution timed out.",
                    "success": False,
                    "language": "python",
                },
                status=status.HTTP_200_OK,
            )
        except FileNotFoundError:
            return Response(
                {
                    "output": "Python interpreter not available on the server.",
                    "success": False,
                    "language": "python",
                },
                status=status.HTTP_200_OK,
            )

        output = stdout if returncode == 0 else (stderr or stdout)
        if not output:
            output = "(no output)"

        return Response(
            {
                "output": output,
                "success": returncode == 0,
                "language": "python",
            }
        )

    def _run_rust(self, code: str):
        payload = json.dumps(
            {
                "code": code,
                "crateType": "bin",
                "mode": "debug",
                "edition": "2021",
                "channel": "stable",
                "tests": False,
            }
        ).encode("utf-8")

        req = Request(
            self.RUST_PLAYGROUND_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            resp = urlopen(req, timeout=self.REQUEST_TIMEOUT)
            body = json.loads(resp.read().decode("utf-8"))
        except URLError as e:
            logger.warning("Rust playground request failed: %s", e)
            return Response(
                {"detail": f"Rust playground error: {e.reason}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except json.JSONDecodeError:
            return Response(
                {"detail": "Invalid response from Rust playground."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except TimeoutError:
            return Response(
                {"detail": "Rust playground timed out."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )

        stdout = body.get("stdout", "")
        stderr = body.get("stderr", "")
        success = body.get("success", False)

        output = stdout if success else (stderr or stdout)
        if not output:
            output = "(no output)"

        return Response(
            {
                "output": output,
                "success": success,
                "language": "rust",
            }
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
