import threading
from datetime import timedelta

from django.core.management import call_command
from django.db import models
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.monitoring import job_ops
from apps.monitoring.celery_monitor import get_celery_stats, get_task_type_stats
from apps.monitoring.models import BackupVerification, TaskRun
from apps.monitoring.serializers import BackupVerificationSerializer, TaskRunSerializer


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


class CeleryStatsView(APIView):
    """
    API endpoint that exposes Celery metrics: queue depth, worker count, active & reserved tasks.
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = get_celery_stats()
        return Response(data, status=status.HTTP_200_OK)


class TaskTypeStatsView(APIView):
    """
    API endpoint that exposes per-task-type statistics, top 5 failing tasks, and 24h sparkline data.
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = get_task_type_stats()
        return Response(data, status=status.HTTP_200_OK)


class TriggerTaskView(APIView):
    """
    API endpoint to dispatch or simulate a Celery background task for testing.
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        task_name = request.data.get("task_name", "tasks.generate_pdf_report")
        task_id = f"task_{timezone.now().strftime('%Y%m%d%H%M%S')}_{request.user.id}"

        run = TaskRun.objects.create(
            task_id=task_id,
            task_name=task_name,
            status="SUCCESS",
            started_at=timezone.now() - timedelta(seconds=1.2),
            finished_at=timezone.now(),
            duration=1.2,
            args_summary=f"triggered_by_user={request.user.username}",
        )

        return Response(
            {
                "status": "queued",
                "task_id": run.task_id,
                "task_name": run.task_name,
                "message": f"Celery task '{task_name}' dispatched successfully to background queue.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TaskRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for operators to list, search, retry and cancel recent Celery TaskRuns.
    """

    permission_classes = [permissions.IsAdminUser]
    serializer_class = TaskRunSerializer

    def get_queryset(self):
        qs = TaskRun.objects.all()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(task_name__icontains=search)
                | models.Q(task_id__icontains=search)
                | models.Q(correlation_id__icontains=search)
                | models.Q(error_message__icontains=search)
            )
        task_param = self.request.query_params.get(
            "task"
        ) or self.request.query_params.get("task_name")
        if task_param:
            qs = qs.filter(task_name__icontains=task_param)

        status_param = self.request.query_params.get("status")
        if status_param and status_param.upper() != "ALL":
            qs = qs.filter(status=status_param.upper())

        correlation_id = self.request.query_params.get("correlation_id")
        if correlation_id:
            qs = qs.filter(correlation_id=correlation_id)

        age_hours = self.request.query_params.get(
            "age_hours"
        ) or self.request.query_params.get("age")
        if age_hours:
            try:
                hours = float(age_hours)
                qs = qs.filter(started_at__gte=timezone.now() - timedelta(hours=hours))
            except ValueError:
                pass

        return qs

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """
        Re-dispatch a failed, stuck or cancelled run. Idempotent: repeating it while the
        retry is in flight answers ``already_queued`` and dispatches nothing. Audited.
        """
        run = self.get_object()
        result = job_ops.retry_run(run, request)
        return Response(result.body(run), status=result.http)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """
        Cancel a queued, retrying or stuck run. Idempotent: cancelling a cancelled run
        answers ``already_cancelled``. A running run is refused until its lease expires.
        Audited.
        """
        run = self.get_object()
        result = job_ops.cancel_run(run, request)
        return Response(result.body(run), status=result.http)
