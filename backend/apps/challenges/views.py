import json
import logging
import re

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Challenge, ChallengeCompletion, ChallengeOfTheDay
from .serializers import ChallengeSerializer
from .throttles import SandboxAnonRateThrottle, SandboxUserRateThrottle

logger = logging.getLogger(__name__)



class ChallengeViewSet(viewsets.ModelViewSet):
    """Existing view — untouched."""

    serializer_class = ChallengeSerializer

    def get_permissions(self):
        from apps.rbac.permissions import HasPermission
        from rest_framework import permissions

        if self.action in ["create"]:
            return [permissions.IsAuthenticated(), HasPermission("create_content")]
        elif self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("edit_content")]
        elif self.action in ["destroy"]:
            return [permissions.IsAuthenticated(), HasPermission("delete_content")]
        return [permissions.AllowAny()]

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

        Executes the submitted code using the same hardened execution engine
        the WebSocket sandbox consumer uses (AST whitelist, memory/CPU
        limits, subprocess isolation, timeouts, and concurrency limits —
        see apps.sandbox.services.stream_python_execution and
        apps.sandbox.resource_manager.ResourceManagementEngine).
        """

        code = request.data.get("code", "")
        language = request.data.get("language", "python")

        if not code:
            return Response(
                {"detail": "No code provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        if language != "python":
            return Response(
                {
                    "detail": (
                        f"Language '{language}' is not supported yet. "
                        "Only 'python' is currently executable."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from asgiref.sync import async_to_sync

        from apps.sandbox.services import stream_python_execution

        if request.user and request.user.is_authenticated:
            user_id = str(request.user.id)
        else:
            # Distinct anonymous identity per client, so the concurrency
            # lock in ResourceManagementEngine doesn't conflate unrelated
            # anonymous users under a single "anonymous" bucket.
            user_id = f"anon:{request.META.get('REMOTE_ADDR', 'unknown')}"

        events = []

        async def send_callback(message_data):
            events.append(message_data)

        # stream_python_execution is async (it's shared with the WebSocket
        # consumer); run it to completion synchronously for this HTTP view.
        async_to_sync(stream_python_execution)(code, send_callback, user_id=user_id)

        stdout = "".join(
            e.get("output", "")
            for e in events
            if e.get("action") == "execution_output" and e.get("type") == "stdout"
        )
        stderr = "".join(
            e.get("output", "")
            for e in events
            if e.get("action") == "execution_output" and e.get("type") == "stderr"
        )

        error_event = next(
            (e for e in events if e.get("action") == "execution_error"), None
        )
        if error_event:
            return Response(
                {"detail": error_event.get("error", "Execution error.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        end_event = next(
            (e for e in events if e.get("action") == "execution_end"), {}
        )

        return Response(
            {
                "language": language,
                "stdout": stdout,
                "stderr": stderr,
                "status": end_event.get("status", "Unknown"),
                "returncode": end_event.get("returncode"),
            },
            status=status.HTTP_200_OK,
        )


class BulkChallengeUploadView(APIView):
    """
    POST /api/challenges/bulk-upload/
    Accepts a JSON file upload to bulk create Challenge records.
    Restricted to users with 'create_content' permission.
    """

    def get_permissions(self):
        from apps.rbac.permissions import HasPermission
        from rest_framework import permissions

        return [permissions.IsAuthenticated(), HasPermission("create_content")]

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
        except json.JSONDecodeError:
            return Response(
                {
                    "error": "Failed to parse JSON. Please ensure the file is valid JSON."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(data, list):
            return Response(
                {
                    "error": "Invalid format: The JSON file must contain a list of objects."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate every row up front. Nothing is written to the database
        # until the whole batch passes, so a bad row never rolls back valid
        # ones after the fact, and callers get a clear, actionable list of
        # what to fix instead of a raw database error.
        row_errors = []
        existing_slugs = set(Challenge.objects.values_list("slug", flat=True))
        seen_slugs_in_batch = set()
        slug_pattern = re.compile(r"^[-a-zA-Z0-9_]+$")

        for index, item in enumerate(data):
            errors = []

            if not isinstance(item, dict):
                row_errors.append({"index": index, "errors": ["Row is not a JSON object."]})
                continue

            title = item.get("title")
            if not title or not str(title).strip():
                errors.append("title is required.")
            elif len(str(title)) > 255:
                errors.append("title must be 255 characters or fewer.")

            slug = item.get("slug")
            if not slug or not str(slug).strip():
                errors.append("slug is required.")
            else:
                slug = str(slug).strip()
                if not slug_pattern.match(slug):
                    errors.append(
                        "slug may only contain letters, numbers, hyphens, and underscores."
                    )
                elif slug in existing_slugs:
                    errors.append(f"slug '{slug}' already exists.")
                elif slug in seen_slugs_in_batch:
                    errors.append(f"slug '{slug}' is duplicated within this upload.")
                else:
                    seen_slugs_in_batch.add(slug)

            points = item.get("points", 50)
            try:
                if int(points) < 0:
                    errors.append("points must be a non-negative integer.")
            except (TypeError, ValueError):
                errors.append("points must be an integer.")

            if errors:
                row_errors.append({"index": index, "errors": errors})

        if row_errors:
            return Response(
                {
                    "error": f"Validation failed for {len(row_errors)} of {len(data)} row(s). No challenges were created.",
                    "row_errors": row_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                challenges_to_create = [
                    Challenge(
                        organization=request.user.organization,
                        title=item.get("title"),
                        slug=item.get("slug"),
                        summary=item.get("summary", ""),
                        difficulty=item.get("difficulty", "beginner"),
                        points=item.get("points", 50),
                        is_featured=item.get("is_featured", False),
                    )
                    for item in data
                ]
                Challenge.objects.bulk_create(challenges_to_create)

            return Response(
                {
                    "message": f"Successfully created {len(challenges_to_create)} challenges."
                },
                status=status.HTTP_201_CREATED,
            )

        except IntegrityError:
            logger.exception("Bulk challenge upload failed a database constraint")
            return Response(
                {
                    "error": "One or more rows conflicted with existing data (e.g. a duplicate slug created concurrently). Please retry the upload."
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception("Unexpected error during bulk challenge upload")
            return Response(
                {"error": "An unexpected error occurred while creating challenges."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChallengeOfTheDayView(APIView):
    """
    GET /api/challenges/today/

    Returns the challenge designated as "Challenge of the Day" for the current
    calendar date, along with the bonus_points on offer and whether the
    authenticated user has already completed it.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate(timezone.now())
        cotd = (
            ChallengeOfTheDay.objects.filter(date=today)
            .select_related("challenge")
            .first()
        )
        if not cotd:
            return Response(
                {"detail": "No challenge set for today."},
                status=status.HTTP_404_NOT_FOUND,
            )

        already_completed = ChallengeCompletion.objects.filter(
            user=request.user, challenge=cotd.challenge
        ).exists()

        data = ChallengeSerializer(cotd.challenge).data
        data["bonus_points"] = cotd.bonus_points
        data["already_completed"] = already_completed
        return Response(data)


class CompleteChallengeOfTheDayView(APIView):
    """
    POST /api/challenges/today/complete/

    Records the authenticated user's completion of today's Challenge of the Day
    and stores the bonus XP earned. Idempotent: returns 400 if already completed.
    Invalidates the contributor dashboard cache so XP is reflected immediately.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        today = timezone.localdate(timezone.now())
        cotd = get_object_or_404(ChallengeOfTheDay, date=today)

        with transaction.atomic():
            _, created = ChallengeCompletion.objects.get_or_create(
                user=request.user,
                challenge=cotd.challenge,
                defaults={"bonus_earned": cotd.bonus_points},
            )

        if not created:
            return Response(
                {"detail": "You have already completed today's challenge."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate contributor dashboard cache so XP reflects immediately
        from apps.dashboard.signals import clear_dashboard_caches

        clear_dashboard_caches(user_id=request.user.id)

        return Response(
            {"bonus_earned": cotd.bonus_points},
            status=status.HTTP_201_CREATED,
        )
