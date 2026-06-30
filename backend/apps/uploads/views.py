import os
import shutil
from rest_framework import views, status, permissions
from rest_framework.response import Response
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import UploadSession

class StartUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        filename = request.data.get("filename")
        total_size = request.data.get("total_size")
        total_chunks = request.data.get("total_chunks")

        if not all([filename, total_size, total_chunks]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        session = UploadSession.objects.create(
            user=request.user,
            filename=filename,
            total_size=int(total_size),
            total_chunks=int(total_chunks),
            status=UploadSession.Status.PENDING
        )
        
        # Initialize directory
        session.get_temp_dir()

        return Response({"session_id": session.session_id}, status=status.HTTP_201_CREATED)

class UploadChunkView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = UploadSession.objects.get(session_id=session_id, user=request.user)
        except UploadSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        chunk_index = int(request.data.get("chunk_index", -1))
        file_chunk = request.FILES.get("chunk")

        if chunk_index == -1 or not file_chunk:
            return Response({"error": "Missing chunk data"}, status=status.HTTP_400_BAD_REQUEST)

        if chunk_index in session.uploaded_chunks:
            return Response({"message": "Chunk already uploaded"}, status=status.HTTP_200_OK)

        temp_dir = session.get_temp_dir()
        chunk_path = os.path.join(temp_dir, f"{chunk_index}.part")
        
        with open(chunk_path, "wb+") as destination:
            for chunk in file_chunk.chunks():
                destination.write(chunk)

        session.uploaded_chunks.append(chunk_index)
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

        if len(session.uploaded_chunks) != session.total_chunks:
            return Response({"error": "Missing chunks", "uploaded": session.uploaded_chunks}, status=status.HTTP_400_BAD_REQUEST)

        temp_dir = session.get_temp_dir()
        final_filename = f"{session.session_id}_{session.filename}"
        final_path = os.path.join(settings.MEDIA_ROOT, 'uploads', final_filename)
        
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        with open(final_path, "wb") as final_file:
            for i in range(session.total_chunks):
                chunk_path = os.path.join(temp_dir, f"{i}.part")
                if not os.path.exists(chunk_path):
                    return Response({"error": f"Chunk {i} not found on disk"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                with open(chunk_path, "rb") as c:
                    final_file.write(c.read())

        # Cleanup temp directory
        shutil.rmtree(temp_dir)

        session.status = UploadSession.Status.COMPLETED
        session.file_path = f"uploads/{final_filename}"
        session.save(update_fields=["status", "file_path", "updated_at"])

        return Response({"message": "Upload completed", "file_path": session.file_path}, status=status.HTTP_200_OK)

class UploadStatusView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = UploadSession.objects.get(session_id=session_id, user=request.user)
        except UploadSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "session_id": session.session_id,
            "status": session.status,
            "uploaded_chunks": session.uploaded_chunks,
            "total_chunks": session.total_chunks
        })
