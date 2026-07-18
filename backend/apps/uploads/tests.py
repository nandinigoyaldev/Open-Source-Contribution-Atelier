import tempfile
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.uploads.models import UploadSession

class ChunkedUploadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuploader", password="password123")
        self.client.force_authenticate(user=self.user)

    def test_start_upload_sanitizes_path_traversal_filename(self):
        url = reverse("uploads:start_upload")
        data = {
            "filename": "../../../../etc/cron.d/malicious_cron",
            "total_size": 1000,
            "total_chunks": 2
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session_id = response.data["session_id"]
        
        session = UploadSession.objects.get(session_id=session_id)
        # Should sanitize to basename
        self.assertEqual(session.filename, "malicious_cron")

    def test_upload_flow_success(self):
        # 1. Start Upload
        start_url = reverse("uploads:start_upload")
        start_data = {
            "filename": "testfile.txt",
            "total_size": 20,
            "total_chunks": 2
        }
        response = self.client.post(start_url, start_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session_id = response.data["session_id"]

        # 2. Upload Chunks
        import os
        chunk_url = reverse("uploads:upload_chunk", kwargs={"session_id": session_id})
        
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(b"part1")
            f1.seek(0)
            f1.close()
            with open(f1.name, "rb") as upload_f1:
                res_c1 = self.client.post(chunk_url, {"chunk_index": 0, "chunk": upload_f1}, format="multipart")
                self.assertEqual(res_c1.status_code, status.HTTP_200_OK)
            os.unlink(f1.name)

        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(b"part2")
            f2.seek(0)
            f2.close()
            with open(f2.name, "rb") as upload_f2:
                res_c2 = self.client.post(chunk_url, {"chunk_index": 1, "chunk": upload_f2}, format="multipart")
                self.assertEqual(res_c2.status_code, status.HTTP_200_OK)
            os.unlink(f2.name)

        # 3. Complete Upload
        complete_url = reverse("uploads:complete_upload", kwargs={"session_id": session_id})
        res_complete = self.client.post(complete_url, format="json")
        self.assertEqual(res_complete.status_code, status.HTTP_200_OK)
        
        session = UploadSession.objects.get(session_id=session_id)
        self.assertEqual(session.status, UploadSession.Status.COMPLETED)
