from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from apps.errors.tasks import ingest_error_event_task


class ErrorIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Receives an error payload and immediately offloads it to a Celery task.
        """
        payload = request.data
        if not payload or "message" not in payload:
            return Response(
                {"error": "Missing message field in payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Offload to celery immediately for async high throughput
        ingest_error_event_task.delay(payload)

        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)
