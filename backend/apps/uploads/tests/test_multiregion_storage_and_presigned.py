from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.uploads.models import UploadSession
from config.storage import (
    MediaS3Storage,
    MultiRegionS3Storage,
    StaticS3Storage,
    generate_presigned_upload_url,
)

User = get_user_model()


class MultiRegionStorageTests(TestCase):
    @override_settings(
        AWS_STORAGE_BUCKET_NAME="atelier-primary-test",
        AWS_S3_REGION_NAME="us-east-1",
        AWS_S3_REPLICA_BUCKET_NAME="atelier-replica-test",
        AWS_S3_REPLICA_REGION_NAME="eu-central-1",
        AWS_S3_CUSTOM_DOMAIN="cdn.atelier.dev",
        AWS_S3_REPLICATION_ENABLED=True,
    )
    def test_multiregion_storage_configuration(self):
        storage = MultiRegionS3Storage()
        self.assertEqual(storage.bucket_name, "atelier-primary-test")
        self.assertEqual(storage.region_name, "us-east-1")
        self.assertEqual(storage.replica_bucket_name, "atelier-replica-test")
        self.assertEqual(storage.replica_region_name, "eu-central-1")
        self.assertEqual(storage.custom_domain, "cdn.atelier.dev")
        self.assertEqual(
            storage.object_parameters.get("CacheControl"),
            "public, max-age=31536000, immutable",
        )

    @override_settings(
        AWS_S3_CUSTOM_DOMAIN="cdn.atelier.dev",
    )
    def test_custom_domain_url_generation(self):
        storage = MediaS3Storage()
        url = storage.url("uploads/avatar.png")
        self.assertTrue(url.startswith("https://cdn.atelier.dev/"))
        self.assertIn("uploads/avatar.png", url)

    def test_static_and_media_storage_classes(self):
        media_storage = MediaS3Storage()
        self.assertEqual(media_storage.location, "media")
        self.assertFalse(media_storage.file_overwrite)
        self.assertEqual(
            media_storage.object_parameters.get("CacheControl"),
            "public, max-age=31536000, immutable",
        )

        static_storage = StaticS3Storage()
        self.assertEqual(static_storage.location, "static")


class PresignedUploadUrlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="presign_user", email="presign@example.com", password="password123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("boto3.client")
    def test_generate_presigned_upload_url(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://atelier-primary.s3.amazonaws.com/media/uploads/user_1/file.png?X-Amz-Signature=xyz"
        mock_boto_client.return_value = mock_s3

        res = generate_presigned_upload_url(
            filename="document.pdf",
            content_type="application/pdf",
            user_id=str(self.user.id),
        )

        self.assertEqual(res["method"], "PUT")
        self.assertIn("https://", res["upload_url"])
        self.assertIn("document.pdf", res["s3_key"])
        self.assertEqual(res["headers"]["Content-Type"], "application/pdf")
        self.assertEqual(
            res["headers"]["Cache-Control"],
            "public, max-age=31536000, immutable",
        )

    @patch("boto3.client")
    def test_presigned_upload_url_api_view_success(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://atelier-primary.s3.amazonaws.com/media/uploads/user_1/file.png?signature"
        mock_boto_client.return_value = mock_s3

        payload = {
            "filename": "screenshot.png",
            "content_type": "image/png",
            "file_size": 1024 * 50,
            "upload_type": UploadSession.UploadType.PROJECT,
        }

        response = self.client.post(
            "/api/uploads/presigned-url/", payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("upload_url", data)
        self.assertIn("s3_key", data)
        self.assertIn("session_id", data)
        self.assertEqual(data["method"], "PUT")
        self.assertEqual(data["headers"]["Content-Type"], "image/png")
        self.assertEqual(
            data["headers"]["Cache-Control"],
            "public, max-age=31536000, immutable",
        )

    def test_presigned_upload_url_api_view_validation_failure(self):
        # Missing filename
        response = self.client.post(
            "/api/uploads/presigned-url/", {"content_type": "image/png"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid upload type
        response = self.client.post(
            "/api/uploads/presigned-url/",
            {"filename": "test.png", "upload_type": "invalid_type"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
