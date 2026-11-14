import os
import unittest
from unittest.mock import patch
from datetime import timedelta

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.data_exports import datasets
from apps.data_exports.models import ExportJob
from apps.notes.models import Note
from apps.progress.models import Certificate, DailyActivity
from apps.organizations.models import Organization, OrganizationMembership


class PrivacySafeDataExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        datasets.register_default_datasets()

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username=f"exportuser_{os.urandom(4).hex()}",
            email="exportuser@example.com",
            password="password123",
        )
        self.other_user = self.User.objects.create_user(
            username=f"other_{os.urandom(4).hex()}",
            email="other@example.com",
            password="password123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_registered_privacy_datasets(self):
        """Verify notes, certificates, organizations, and daily_activity datasets are registered."""
        all_keys = [d.key for d in datasets.all_datasets()]
        self.assertIn("notes", all_keys)
        self.assertIn("certificates", all_keys)
        self.assertIn("organizations", all_keys)
        self.assertIn("daily_activity", all_keys)

    def test_notes_excludes_encryption_iv(self):
        """Verify notes dataset excludes 'iv' to protect cryptographic privacy."""
        notes_dataset = datasets.get_dataset("notes")
        self.assertIn("iv", notes_dataset.exclude)
        self.assertNotIn("iv", notes_dataset.columns)
        self.assertIn("title", notes_dataset.columns)
        self.assertIn("encrypted_content", notes_dataset.columns)

    def test_organization_membership_user_isolation(self):
        """Verify organization dataset only returns records belonging to the requesting user."""
        org1 = Organization.objects.create(name=f"Org One {os.urandom(4).hex()}")
        org2 = Organization.objects.create(name=f"Org Two {os.urandom(4).hex()}")

        mem1 = OrganizationMembership.objects.create(organization=org1, user=self.user, role="admin")
        mem2 = OrganizationMembership.objects.create(organization=org2, user=self.other_user, role="owner")

        org_dataset = datasets.get_dataset("organizations")
        qs = org_dataset.queryset(self.user)

        self.assertIn(mem1, qs)
        self.assertNotIn(mem2, qs)
        self.assertEqual(qs.count(), 1)

    def test_documented_exclusions_content(self):
        """Verify documented exclusions cover passwords, tokens, IVs, and tenant scoping."""
        exclusions = datasets.get_documented_exclusions()
        self.assertIn("sensitive_fields_excluded", exclusions)
        self.assertIn("passwords", exclusions["sensitive_fields_excluded"])
        self.assertIn("encryption_initialization_vectors", exclusions["sensitive_fields_excluded"])
        self.assertIn("notes", exclusions["dataset_exclusions"])
        self.assertIn("organizations", exclusions["dataset_exclusions"])

    def test_export_documentation_endpoint(self):
        """Verify GET /api/exports/documentation/ returns dataset columns and exclusions."""
        response = self.client.get("/api/exports/documentation/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("datasets", data)
        self.assertIn("documented_exclusions", data)
        self.assertIn("notes", data["datasets"])
        self.assertIn("iv", data["datasets"]["notes"]["excluded_fields"])

    def test_export_list_endpoint_includes_documentation(self):
        """Verify GET /api/exports/ returns documented_exclusions."""
        response = self.client.get("/api/exports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("documented_exclusions", data)
        self.assertIn("datasets", data)

    @patch("apps.data_exports.tasks.enqueue")
    def test_repeat_request_returns_existing_active_job(self, mock_enqueue):
        """Verify submitting a repeat request returns HTTP 200 with the active job instead of duplicate/429."""
        job = ExportJob.objects.create(
            user=self.user,
            dataset="notes",
            file_format="csv",
            status=ExportJob.RUNNING,
            total_rows=5,
        )

        response = self.client.post("/api/exports/", {"dataset": "notes", "format": "csv"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], str(job.id))
        self.assertEqual(data["dataset"], "notes")
        mock_enqueue.assert_not_called()

    def test_cross_user_isolation_export_detail(self):
        """Verify User A cannot access User B's export job."""
        other_job = ExportJob.objects.create(
            user=self.other_user,
            dataset="notes",
            file_format="csv",
            status=ExportJob.COMPLETED,
        )

        response = self.client.get(f"/api/exports/{other_job.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_expired_export_download_returns_410(self):
        """Verify expired export download returns 410 Gone."""
        expired_job = ExportJob.objects.create(
            user=self.user,
            dataset="notes",
            file_format="csv",
            status=ExportJob.EXPIRED,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.get(f"/api/exports/{expired_job.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
