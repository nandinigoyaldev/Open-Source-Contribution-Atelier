from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from apps.rbac.models import Role, UserRole

User = get_user_model()


class RBACIntegrationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_rbac")

        cls.admin_user = User.objects.create_user(username="admin", password="password")
        cls.moderator_user = User.objects.create_user(
            username="mod", password="password"
        )
        cls.contributor_user = User.objects.create_user(
            username="contrib", password="password"
        )
        cls.student_user = User.objects.create_user(
            username="student", password="password"
        )

        admin_role = Role.objects.get(name="Admin")
        mod_role = Role.objects.get(name="Moderator")
        contrib_role = Role.objects.get(name="Contributor")

        UserRole.objects.create(user=cls.admin_user, role=admin_role)
        UserRole.objects.create(user=cls.moderator_user, role=mod_role)
        UserRole.objects.create(user=cls.contributor_user, role=contrib_role)

    def test_lesson_create_requires_permission(self):
        data = {
            "title": "New Lesson",
            "slug": "new-lesson",
            "difficulty": "Beginner",
            "summary": "Sum",
            "content": "Content",
        }

        self.client.force_authenticate(user=self.student_user)
        response = self.client.post("/api/content/lessons/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.contributor_user)
        response = self.client.post("/api/content/lessons/", data)
        # Should not be forbidden. Might fail validation (400), but not 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_dashboard_access(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/dashboard/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.moderator_user)
        response = self.client.get("/api/dashboard/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/dashboard/admin/")
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_analytics_access(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/dashboard/analytics/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.contributor_user)
        response = self.client.get("/api/dashboard/analytics/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.moderator_user)
        response = self.client.get("/api/dashboard/analytics/")
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/dashboard/analytics/")
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
