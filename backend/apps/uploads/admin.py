import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone

from .models import UploadScanHistory, UploadSession


class UploadScanHistoryInline(admin.TabularInline):
    model = UploadScanHistory
    extra = 0
    readonly_fields = ("result", "engine", "signature", "message", "scanned_at", "released_by")
    can_delete = False


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = ("filename", "user", "upload_type", "status", "detected_mime_type", "created_at")
    list_filter = ("status", "upload_type", "detected_mime_type")
    search_fields = ("filename", "user__username", "session_id")
    readonly_fields = ("session_id", "created_at", "updated_at", "scan_started_at", "scan_completed_at")
    actions = ("release_false_positive",)
    inlines = (UploadScanHistoryInline,)

    @admin.action(description="Release selected quarantined files as false positives")
    def release_false_positive(self, request, queryset):
        released = 0
        for upload in queryset.filter(status__in=[UploadSession.Status.QUARANTINED, UploadSession.Status.FAILED]):
            source = Path(upload.quarantine_path)
            if not source.exists():
                continue
            destination_dir = Path(settings.MEDIA_ROOT) / "uploads"
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"{upload.session_id}_{Path(upload.filename).name}"
            shutil.move(str(source), destination)
            upload.file_path = str(destination.relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
            upload.quarantine_path = ""
            upload.status = UploadSession.Status.RELEASED
            upload.scan_message = "Released by an administrator after false-positive review."
            upload.scan_completed_at = timezone.now()
            upload.save()
            UploadScanHistory.objects.create(
                upload=upload,
                result=UploadScanHistory.Result.RELEASED,
                message=upload.scan_message,
                released_by=request.user,
            )
            released += 1
        self.message_user(request, f"Released {released} upload(s).", level=messages.SUCCESS)


@admin.register(UploadScanHistory)
class UploadScanHistoryAdmin(admin.ModelAdmin):
    list_display = ("upload", "result", "engine", "signature", "scanned_at", "released_by")
    list_filter = ("result", "engine")
    search_fields = ("upload__filename", "signature", "message")
    readonly_fields = ("upload", "result", "engine", "signature", "message", "scanned_at", "released_by")
