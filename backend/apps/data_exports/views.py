import re
from typing import cast

from django.http import FileResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import datasets, runner
from .models import ExportJob
from .tasks import enqueue

RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
BLOCK = 64 * 1024


def _active_limit() -> int:
    from django.conf import settings

    return int(getattr(settings, "EXPORT_MAX_ACTIVE_PER_USER", 2))


def serialize(job: ExportJob, request=None) -> dict:
    total = cast("int | None", job.total_rows)
    percent = None
    if job.status == ExportJob.COMPLETED:
        percent = 100
    elif total:
        percent = min(99, int(cast(int, job.rows_written) * 100 / total))
    elif total == 0 and job.status != ExportJob.QUEUED:
        percent = 100 if job.status == ExportJob.COMPLETED else 0
    data = {
        "id": str(job.id),
        "dataset": job.dataset,
        "format": job.file_format,
        "status": job.status,
        "rows_written": job.rows_written,
        "total_rows": total,
        "bytes_written": job.bytes_written,
        "progress_percent": percent,
        "attempts": job.attempts,
        "error": job.error,
        "cancel_requested": job.cancel_requested,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "expires_at": job.expires_at,
        "downloadable": job.is_downloadable,
    }
    if job.is_downloadable:
        data["sha256"] = job.sha256
        if request is not None:
            data["download_url"] = request.build_absolute_uri(
                f"/api/exports/{job.id}/download/"
            )
    return data


class ExportDocumentationView(APIView):
    """Provides privacy, retention, and documented exclusions metadata for account data export."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        datasets_info = {
            d.key: {
                "label": d.label,
                "columns": d.columns,
                "excluded_fields": list(d.exclude),
            }
            for d in datasets.all_datasets()
        }
        return Response(
            {
                "datasets": datasets_info,
                "documented_exclusions": datasets.get_documented_exclusions(),
            }
        )


class ExportListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        jobs = ExportJob.objects.filter(user=request.user)[:50]
        return Response(
            {
                "datasets": [
                    {
                        "key": d.key,
                        "label": d.label,
                        "columns": d.columns,
                        "excluded_fields": list(d.exclude),
                    }
                    for d in datasets.all_datasets()
                ],
                "formats": [f for f, _ in ExportJob.FORMAT_CHOICES],
                "documented_exclusions": datasets.get_documented_exclusions(),
                "results": [serialize(j, request) for j in jobs],
            }
        )

    def post(self, request):
        key = request.data.get("dataset")
        file_format = request.data.get("format", "csv")
        try:
            dataset = datasets.get_dataset(str(key))
        except datasets.UnknownDataset:
            return Response(
                {
                    "error": "unknown_dataset",
                    "datasets": [d.key for d in datasets.all_datasets()],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_format not in dict(ExportJob.FORMAT_CHOICES):
            return Response(
                {
                    "error": "unsupported_format",
                    "formats": [f for f, _ in ExportJob.FORMAT_CHOICES],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Repeat request handling: if an export for this dataset and format is already running/queued,
        # return the existing job gracefully rather than erroring or creating duplicates.
        existing_active = (
            ExportJob.objects.filter(
                user=request.user,
                dataset=dataset.key,
                file_format=file_format,
                status__in=ExportJob.ACTIVE_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )
        if existing_active:
            return Response(serialize(existing_active, request), status=status.HTTP_200_OK)

        active = ExportJob.objects.filter(
            user=request.user, status__in=ExportJob.ACTIVE_STATUSES
        ).count()
        if active >= _active_limit():
            return Response(
                {
                    "error": "too_many_active_exports",
                    "detail": "Wait for a running export to finish or cancel it.",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        job = ExportJob.objects.create(
            user=request.user,
            dataset=dataset.key,
            file_format=file_format,
            total_rows=datasets.count_rows(dataset, request.user),
        )
        enqueue(job.id)
        job.refresh_from_db()
        return Response(serialize(job, request), status=status.HTTP_202_ACCEPTED)


class ExportDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        job = get_object_or_404(ExportJob, pk=pk, user=request.user)
        return Response(serialize(job, request))


class ExportCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        job = get_object_or_404(ExportJob, pk=pk, user=request.user)
        if not job.is_active:
            return Response(
                {"error": "not_active", "status": job.status},
                status=status.HTTP_409_CONFLICT,
            )
        ExportJob.objects.filter(
            pk=job.pk, status__in=ExportJob.ACTIVE_STATUSES
        ).update(cancel_requested=True)
        # A job that has not started has no worker to notice the request: cancel it right away.
        cancelled = ExportJob.objects.filter(pk=job.pk, status=ExportJob.QUEUED).update(
            status=ExportJob.CANCELLED, finished_at=timezone.now()
        )
        if cancelled:
            runner.remove_file(runner.part_path(job))
        job.refresh_from_db()
        return Response(serialize(job, request), status=status.HTTP_202_ACCEPTED)


class ExportDownloadView(APIView):
    """Download a finished export. Supports ``Range`` so an interrupted download can resume."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        job = get_object_or_404(ExportJob, pk=pk, user=request.user)
        if job.status == ExportJob.EXPIRED or (
            job.status == ExportJob.COMPLETED and not job.is_downloadable
        ):
            return Response({"error": "expired"}, status=status.HTTP_410_GONE)
        if job.status != ExportJob.COMPLETED:
            return Response(
                {"error": "not_ready", "status": job.status},
                status=status.HTTP_409_CONFLICT,
            )

        path = runner.export_root() / job.file_name
        if not path.is_file():
            return Response({"error": "expired"}, status=status.HTTP_410_GONE)

        size = path.stat().st_size
        filename = f"{job.dataset}-{job.created_at:%Y%m%d}.{job.file_format}"
        content_type = runner.CONTENT_TYPES[job.file_format]
        headers = {
            "Accept-Ranges": "bytes",
            "ETag": f'"{job.sha256}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        }

        spec = request.headers.get("Range")
        if not spec:
            response = FileResponse(
                open(path, "rb"),
                as_attachment=True,
                filename=filename,
                content_type=content_type,
            )
            for key, value in headers.items():
                response[key] = value
            response["Content-Length"] = str(size)
            return response

        match = RANGE.match(spec.strip())
        start = end = None
        if match and (match.group(1) or match.group(2)):
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
            else:  # "bytes=-N": the last N bytes
                start = max(0, size - int(match.group(2)))
                end = size - 1
            end = min(end, size - 1)
        if start is None or end is None or start >= size or end < start:
            response = Response(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
            response["Content-Range"] = f"bytes */{size}"
            return response

        length = end - start + 1

        def stream():
            with open(path, "rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    block = fh.read(min(BLOCK, left))
                    if not block:
                        break
                    left -= len(block)
                    yield block

        response = StreamingHttpResponse(
            stream(), status=206, content_type=content_type
        )
        for key, value in headers.items():
            response[key] = value
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
        response["Content-Length"] = str(length)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
