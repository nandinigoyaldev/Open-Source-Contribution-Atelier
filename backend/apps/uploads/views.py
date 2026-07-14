import os
import shutil
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import UploadSession
from .tasks import enqueue_upload_scan
from .validators import sanitize_svg_file, validate_declared_size, validate_file


class StartUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        filename = Path(str(request.data.get("filename", ""))).name
        total_size = request.data.get("total_size")
        total_chunks = request.data.get("total_chunks")
        upload_type = request.data.get("upload_type", UploadSession.UploadType.PROJECT)

        if not filename or total_size is None or total_chunks is None:
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        if upload_type not in UploadSession.UploadType.values:
            return Response({"error": "Invalid upload type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            total_size = int(total_size)
            total_chunks = int(total_chunks)
            if total_chunks <= 0:
                raise ValueError
            validate_declared_size(total_size, upload_type)
        except (TypeError, ValueError, ValidationError) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else "Invalid upload metadata"
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        session = UploadSession.objects.create(
            user=request.user,
            filename=get_valid_filename(filename),
            upload_type=upload_type,
            total_size=total_size,
            total_chunks=total_chunks,
        )
        session.get_temp_dir()
        return Response(
            {"session_id": session.session_id, "upload_id": session.session_id, "status": session.status},
            status=status.HTTP_201_CREATED,
        )


class UploadChunkView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = UploadSession.objects.get(session_id=session_id, user=request.user)
        except UploadSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            chunk_index = int(request.data.get("chunk_index", -1))
        except (TypeError, ValueError):
            chunk_index = -1
        file_chunk = request.FILES.get("chunk")

        if chunk_index < 0 or chunk_index >= session.total_chunks or not file_chunk:
            return Response({"error": "Invalid or missing chunk data"}, status=status.HTTP_400_BAD_REQUEST)
        if session.status not in {UploadSession.Status.PENDING, UploadSession.Status.UPLOADING}:
            return Response({"error": "Upload no longer accepts chunks"}, status=status.HTTP_409_CONFLICT)
        if chunk_index in session.uploaded_chunks:
            return Response({"message": "Chunk already uploaded"}, status=status.HTTP_200_OK)

        chunk_path = os.path.join(session.get_temp_dir(), f"{chunk_index}.part")
        with open(chunk_path, "wb+") as destination:
            for chunk in file_chunk.chunks():
                destination.write(chunk)

        session.uploaded_chunks = [*session.uploaded_chunks, chunk_index]
        session.status = UploadSession.Status.UPLOADING
        session.save(update_fields=["uploaded_chunks", "status", "updated_at"])
        return Response({"message": "Chunk uploaded successfully"}, status=status.HTTP_200_OK)


class CompleteUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = UploadSession.objects.get(session_id=session_id, user=request.user)
        except UploadSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if len(set(session.uploaded_chunks)) != session.total_chunks:
            return Response(
                {"error": "Missing chunks", "uploaded": session.uploaded_chunks},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temp_dir = session.get_temp_dir()
        quarantine_root = Path(getattr(settings, "UPLOAD_QUARANTINE_ROOT", settings.BASE_DIR / "quarantine"))
        quarantine_root.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_root / f"{session.session_id}_{session.filename}"

        try:
            with quarantine_path.open("wb") as final_file:
                for index in range(session.total_chunks):
                    chunk_path = Path(temp_dir) / f"{index}.part"
                    if not chunk_path.exists():
                        raise FileNotFoundError(f"Chunk {index} not found on disk")
                    with chunk_path.open("rb") as chunk_file:
                        shutil.copyfileobj(chunk_file, final_file)

            if quarantine_path.stat().st_size != session.total_size:
                raise ValidationError("Uploaded size does not match declared size.")

            detected_type, mime_type = validate_file(
                quarantine_path, session.filename, session.upload_type
            )
            if detected_type == "svg":
                sanitize_svg_file(quarantine_path)
        except (ValidationError, FileNotFoundError) as exc:
            quarantine_path.unlink(missing_ok=True)
            session.status = UploadSession.Status.REJECTED
            session.scan_message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            session.save(update_fields=["status", "scan_message", "updated_at"])
            return Response({"error": session.scan_message}, status=status.HTTP_400_BAD_REQUEST)
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
            session = UploadSession.objects.get(session_id=session_id, user=request.user)
        except UploadSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "session_id": session.session_id,
            "upload_id": session.session_id,
            "status": session.status,
            "message": session.scan_message,
            "uploaded_chunks": session.uploaded_chunks,
            "total_chunks": session.total_chunks,
            "mime_type": session.detected_mime_type,
            "file_path": session.file_path if session.is_accessible else None,
        }
        return Response(payload)
