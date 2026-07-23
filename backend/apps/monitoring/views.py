from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.management import call_command
from apps.monitoring.models import BackupVerification
from apps.monitoring.serializers import BackupVerificationSerializer
from datetime import timedelta
from django.utils import timezone
import threading


class BackupVerificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows admins to view backup verification history and trigger a manual restore verification.
    """

    permission_classes = [permissions.IsAdminUser]
    serializer_class = BackupVerificationSerializer

    def get_queryset(self):
        # Default to last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        return BackupVerification.objects.filter(
            verification_timestamp__gte=thirty_days_ago
        )

    @action(detail=False, methods=["post"])
    def verify_now(self, request):
        """
        Triggers a manual backup verification in the background.
        """

        def run_verify():
            call_command("verify_backup")

        thread = threading.Thread(target=run_verify)
        thread.start()

        return Response(
            {"detail": "Backup verification started in background."},
            status=status.HTTP_202_ACCEPTED,
        )
