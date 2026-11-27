import os
import shutil
import unicodedata
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.urls import reverse
from django.utils.text import get_valid_filename
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import UploadSession
from .tasks import enqueue_upload_scan
from .validators import (
    max_size_for,
    sanitize_svg_file,
    validate_declared_size,
    validate_file,
    validate_filename_extensions,
)


def sanitize_filename_ascii(filename: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    valid = get_valid_filename(ascii_name)
    if not valid or valid.startswith("."):
        valid = f"file_{uuid.uuid4().hex[:8]}{valid}"
    return valid


class StartUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        filename = Path(str(request.data.get("filename", ""))).name
        total_size = request.data.get("total_size")
        total_chunks = request.data.get("total_chunks")
        upload_type = request.data.get("upload_type", UploadSession.UploadType.PROJECT)

        if not filename or total_size is None or total_chunks is None:
            return Response(
                {"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST
            )
        if upload_type not in UploadSession.UploadType.values:
            return Response(
                {"error": "Invalid upload type"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_filename_extensions(filename)
            total_size = int(total_size)
            total_chunks = int(total_chunks)
            if total_chunks <= 0:
                raise ValueError
            validate_declared_size(total_size, upload_type)
        except (TypeError, ValueError, ValidationError) as exc:
            message = (
                exc.messages[0]
                if isinstance(exc, ValidationError)
                else "Invalid upload metadata"
            )
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        session = UploadSession.objects.create(
            user=request.user,
            filename=sanitize_filename_ascii(filename),
            upload_type=upload_type,
            total_size=total_size,
            total_chunks=total_chunks,
        )
        session.get_temp_dir()
        return Response(
            {
                "session_id": session.session_id,
                "upload_id": session.session_id,
                "status": session.status,
            },
            status=status.HTTP_201_CREATED,
        )


class UploadChunkView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = UploadSession.objects.get(
                session_id=session_id, user=request.user
            )
        except UploadSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            chunk_index = int(request.data.get("chunk_index", -1))
        except (TypeError, ValueError):
            chunk_index = -1
        file_chunk = request.FILES.get("chunk")

        if chunk_index < 0 or chunk_index >= session.total_chunks or not file_chunk:
            return Response(
                {"error": "Invalid or missing chunk data"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if session.status not in {
            UploadSession.Status.PENDING,
            UploadSession.Status.UPLOADING,
        }:
            return Response(
                {"error": "Upload no longer accepts chunks"},
                status=status.HTTP_409_CONFLICT,
            )
        if chunk_index in session.uploaded_chunks:
            return Response(
                {"message": "Chunk already uploaded"}, status=status.HTTP_200_OK
            )

        MAX_CHUNK_SIZE = 10 * 1024 * 1024
        if file_chunk.size > MAX_CHUNK_SIZE:
            return Response(
                {"error": "Chunk size exceeds maximum allowed limit of 10MB"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temp_dir = session.get_temp_dir()
        chunk_path = os.path.join(temp_dir, f"{chunk_index}.part")
        with open(chunk_path, "wb+") as destination:
            for chunk in file_chunk.chunks():
                destination.write(chunk)

        max_allowed = max_size_for(session.upload_type)
        current_total = sum(
            os.path.getsize(os.path.join(temp_dir, f))
            for f in os.listdir(temp_dir)
            if f.endswith(".part")
        )
        if current_total > max_allowed:
            os.remove(chunk_path)
            return Response(
                {
                    "error": f"Total uploaded size exceeds allowed limit of {max_allowed // (1024 * 1024)}MB for {session.upload_type}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.uploaded_chunks = [*session.uploaded_chunks, chunk_index]
        session.status = UploadSession.Status.UPLOADING
        session.save(update_fields=["uploaded_chunks", "status", "updated_at"])

        return Response(
            {"message": "Chunk uploaded successfully"}, status=status.HTTP_200_OK
        )


class CompleteUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = UploadSession.objects.get(
                session_id=session_id, user=request.user
            )
        except UploadSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # The JSON field is only bookkeeping and is vulnerable to lost updates
        # when chunks arrive concurrently. The files on disk are the authoritative
        # completion state because every successful chunk write creates one .part.
        temp_dir = Path(session.get_temp_dir())
        uploaded_files = {}
        if temp_dir.exists():
            for chunk_path in temp_dir.glob("*.part"):
                try:
                    index = int(chunk_path.stem)
                except ValueError:
                    continue
                if 0 <= index < session.total_chunks:
                    uploaded_files[index] = chunk_path

        expected_indexes = set(range(session.total_chunks))
        uploaded_indexes = set(uploaded_files)
        if uploaded_indexes != expected_indexes:
            return Response(
                {
                    "error": "Missing chunks",
                    "uploaded": sorted(uploaded_indexes),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Repair stale bookkeeping after observing a complete set on disk.
        if set(session.uploaded_chunks) != expected_indexes:
            session.uploaded_chunks = sorted(uploaded_indexes)
            session.status = UploadSession.Status.UPLOADING
            session.save(update_fields=["uploaded_chunks", "status", "updated_at"])

        quarantine_root = Path(
            getattr(
                settings, "UPLOAD_QUARANTINE_ROOT", settings.BASE_DIR / "quarantine"
            )
        )
        quarantine_root.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_root / f"{session.session_id}_{session.filename}"

        try:
            with quarantine_path.open("wb") as final_file:
                for index in range(session.total_chunks):
                    chunk_path = uploaded_files[index]
                    with chunk_path.open("rb") as chunk_file:
                        shutil.copyfileobj(chunk_file, final_file)

            assembled_size = quarantine_path.stat().st_size
            if assembled_size != session.total_size:
                raise ValidationError("Uploaded size does not match declared size.")

            upload_limit = max_size_for(session.upload_type)
            if assembled_size > upload_limit:
                quarantine_path.unlink(missing_ok=True)
                session.status = UploadSession.Status.FAILED
                session.save(update_fields=["status", "updated_at"])
                raise ValidationError(
                    f"Assembled file size ({assembled_size} bytes) exceeds the "
                    f"{upload_limit // (1024 * 1024)}MB limit for {session.upload_type} uploads."
                )

            detected_type, mime_type = validate_file(
                quarantine_path, session.filename, session.upload_type
            )
            if detected_type == "svg":
                sanitize_svg_file(quarantine_path)
        except (ValidationError, FileNotFoundError) as exc:
            quarantine_path.unlink(missing_ok=True)
            if session.status != UploadSession.Status.FAILED:
                session.status = UploadSession.Status.REJECTED
            session.scan_message = (
                exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            )
            session.save(update_fields=["status", "scan_message", "updated_at"])
            return Response(
                {"error": session.scan_message}, status=status.HTTP_400_BAD_REQUEST
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        session.status = UploadSession.Status.QUARANTINED
        session.detected_mime_type = mime_type
        session.quarantine_path = str(quarantine_path)
        session.scan_message = "File is being scanned..."
        session.save()
        enqueue_upload_scan(str(session.session_id))

        return Response(
            {
                "message": "File is being scanned...",
                "upload_id": session.session_id,
                "session_id": session.session_id,
                "status": session.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class UploadStatusView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            if request.user.is_staff or request.user.is_superuser:
                session = UploadSession.objects.get(session_id=session_id)
            else:
                session = UploadSession.objects.get(
                    session_id=session_id, user=request.user
                )
        except UploadSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )

        download_url = None
        if session.is_accessible:
            download_url = request.build_absolute_uri(
                reverse(
                    "uploads:download_upload", kwargs={"session_id": session.session_id}
                )
            )

        history_items = [
            {
                "result": h.result,
                "engine": h.engine,
                "signature": h.signature,
                "message": h.message,
                "scanned_at": h.scanned_at.isoformat() if h.scanned_at else None,
            }
            for h in session.scan_history.all()[:10]
        ]

        failed_statuses = {
            UploadSession.Status.FAILED,
            getattr(UploadSession.Status, "SCAN_FAILED", "scan_failed"),
            UploadSession.Status.QUARANTINED,
        }

        payload = {
            "session_id": session.session_id,
            "upload_id": session.session_id,
            "filename": session.filename,
            "status": session.status,
            "message": session.scan_message,
            "is_accessible": session.is_accessible,
            "is_clean": session.status
            in {
                UploadSession.Status.CLEAN,
                UploadSession.Status.RELEASED,
            },
            "retryable": session.status in failed_statuses,
            "uploaded_chunks": session.uploaded_chunks,
            "total_chunks": session.total_chunks,
            "mime_type": session.detected_mime_type,
            "file_path": session.file_path if session.is_accessible else None,
            "download_url": download_url,
            "scan_history": history_items,
        }
        return Response(payload)


class DirectUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        uploaded_file = request.FILES.get("file") or request.FILES.get("image")
        if not uploaded_file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )

        upload_type = request.data.get("upload_type", UploadSession.UploadType.PROJECT)
        if upload_type not in UploadSession.UploadType.values:
            return Response(
                {"error": "Invalid upload type"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_declared_size(uploaded_file.size, upload_type)
        except ValidationError as exc:
            return Response(
                {"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST
            )

        valid_name = sanitize_filename_ascii(uploaded_file.name)
        quarantine_root = Path(
            getattr(
                settings, "UPLOAD_QUARANTINE_ROOT", settings.BASE_DIR / "quarantine"
            )
        )
        quarantine_root.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_root / f"{uuid.uuid4()}_{valid_name}"

        with open(quarantine_path, "wb+") as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        try:
            detected_type, mime_type = validate_file(
                quarantine_path, valid_name, upload_type
            )
            if detected_type == "svg":
                sanitize_svg_file(quarantine_path)
        except (ValidationError, FileNotFoundError) as exc:
            quarantine_path.unlink(missing_ok=True)
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        session = UploadSession.objects.create(
            user=request.user,
            filename=valid_name,
            upload_type=upload_type,
            total_size=uploaded_file.size,
            total_chunks=1,
            uploaded_chunks=[0],
            status=UploadSession.Status.QUARANTINED,
            detected_mime_type=mime_type,
            quarantine_path=str(quarantine_path),
            scan_message="File is being scanned...",
        )
        enqueue_upload_scan(str(session.session_id))

        return Response(
            {
                "message": "File is being scanned...",
                "upload_id": session.session_id,
                "session_id": session.session_id,
                "status": session.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DownloadUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            if request.user.is_staff or request.user.is_superuser:
                session = UploadSession.objects.get(session_id=session_id)
            else:
                session = UploadSession.objects.get(
                    session_id=session_id, user=request.user
                )
        except UploadSession.DoesNotExist:
            return Response(
                {"error": "Upload not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if session.status in {
            UploadSession.Status.PENDING,
            UploadSession.Status.UPLOADING,
            UploadSession.Status.QUARANTINED,
            UploadSession.Status.SCANNING,
        }:
            return Response(
                {
                    "error": "File is currently in quarantine pending security scanning.",
                    "status": session.status,
                    "actionable": "Please wait for scan completion before accessing.",
                },
                status=status.HTTP_423_LOCKED,
            )

        if session.status == UploadSession.Status.INFECTED:
            return Response(
                {
                    "error": "File was flagged as infected and cannot be accessed.",
                    "status": session.status,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        failed_statuses = {
            UploadSession.Status.REJECTED,
            UploadSession.Status.FAILED,
            getattr(UploadSession.Status, "SCAN_FAILED", "scan_failed"),
        }
        if session.status in failed_statuses:
            return Response(
                {
                    "error": f"File scan failed ({session.status}). File remains quarantined.",
                    "status": session.status,
                    "message": session.scan_message,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not session.is_accessible:
            return Response(
                {"error": "File is not accessible.", "status": session.status},
                status=status.HTTP_403_FORBIDDEN,
            )

        media_root = Path(settings.MEDIA_ROOT).resolve()
        target_path = (media_root / session.file_path).resolve()
        try:
            target_path.relative_to(media_root)
        except ValueError:
            return Response(
                {"error": "Invalid storage path detected."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not target_path.is_file():
            return Response(
                {"error": "File not found on storage backend"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            open(target_path, "rb"),
            as_attachment=True,
            filename=session.filename,
            content_type=session.detected_mime_type or "application/octet-stream",
        )


class RetryScanView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            if request.user.is_staff or request.user.is_superuser:
                session = UploadSession.objects.get(session_id=session_id)
            else:
                session = UploadSession.objects.get(
                    session_id=session_id, user=request.user
                )
        except UploadSession.DoesNotExist:
            return Response(
                {"error": "Upload not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if session.status in {
            UploadSession.Status.CLEAN,
            UploadSession.Status.RELEASED,
        }:
            return Response(
                {"error": "File is already verified clean.", "status": session.status},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if session.status == UploadSession.Status.INFECTED and not (
            request.user.is_staff or request.user.is_superuser
        ):
            return Response(
                {
                    "error": "Infected uploads cannot be retried.",
                    "status": session.status,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not session.quarantine_path or not os.path.exists(session.quarantine_path):
            return Response(
                {
                    "error": "Quarantined file is missing or expired.",
                    "status": session.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.status = UploadSession.Status.QUARANTINED
        session.scan_message = "Scan re-queued by user/operator..."
        session.save(update_fields=["status", "scan_message", "updated_at"])
        enqueue_upload_scan(str(session.session_id))

        return Response(
            {
                "message": "Scan re-queued successfully.",
                "upload_id": session.session_id,
                "status": session.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PresignedUploadUrlView(views.APIView):
    """
    Generates a pre-authenticated S3 PUT upload URL for direct client-to-storage uploads.
    Reduces application server memory usage by having clients PUT payloads directly to S3/CDN.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        filename = request.data.get("filename")
        content_type = request.data.get("content_type", "application/octet-stream")
        file_size = request.data.get("file_size") or request.data.get("size")
        upload_type = request.data.get("upload_type", UploadSession.UploadType.PROJECT)
        prefix = request.data.get("prefix", "media/uploads")

        if not filename:
            return Response(
                {"error": "Missing 'filename' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if upload_type not in UploadSession.UploadType.values:
            return Response(
                {"error": "Invalid upload type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_filename_extensions(filename)
            if file_size is not None:
                validate_declared_size(int(file_size), upload_type)
        except (TypeError, ValueError, ValidationError) as exc:
            msg = (
                exc.messages[0]
                if isinstance(exc, ValidationError)
                else "Invalid metadata"
            )
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        from config.storage import generate_presigned_upload_url

        user_id = str(request.user.id) if request.user else "anon"
        presigned_data = generate_presigned_upload_url(
            filename=filename,
            content_type=content_type,
            user_id=user_id,
            prefix=prefix,
            max_size_bytes=int(file_size) if file_size else 100 * 1024 * 1024,
        )

        session = UploadSession.objects.create(
            user=request.user,
            filename=sanitize_filename_ascii(filename),
            upload_type=upload_type,
            total_size=int(file_size) if file_size else 0,
            total_chunks=1,
            uploaded_chunks=[0],
            file_path=presigned_data["s3_key"],
            status=UploadSession.Status.CLEAN,
            detected_mime_type=content_type,
        )

        presigned_data["session_id"] = str(session.session_id)
        presigned_data["upload_id"] = str(session.session_id)

        return Response(presigned_data, status=status.HTTP_201_CREATED)
