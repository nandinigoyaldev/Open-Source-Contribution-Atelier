from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Project, ProjectFile

User = get_user_model()


class ProjectTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="password")
        self.user2 = User.objects.create_user(username="user2", password="password")
        self.project_url = reverse("project-list")
        self.file_url = reverse("projectfile-list")

    def test_create_project_unauthenticated(self):
        response = self.client.post(self.project_url, {"name": "Test Project"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_project_authenticated(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.project_url, {"name": "Test Project"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Project.objects.first().user, self.user1)

    def test_project_isolation(self):
        Project.objects.create(user=self.user1, name="User1 Project")
        Project.objects.create(user=self.user2, name="User2 Project")

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.project_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "User1 Project")

    def test_create_project_file(self):
        project = Project.objects.create(user=self.user1, name="Proj1")
        self.client.force_authenticate(user=self.user1)

        data = {
            "project": str(project.id),
            "path": "src/index.js",
            "content": "console.log('test')",
            "language": "javascript",
        }
        response = self.client.post(self.file_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectFile.objects.count(), 1)

    def test_duplicate_file_path_constraint(self):
        project = Project.objects.create(user=self.user1, name="Proj1")
        ProjectFile.objects.create(project=project, path="src/index.js")

        self.client.force_authenticate(user=self.user1)
        data = {
            "project": str(project.id),
            "path": "src/index.js",
            "content": "new content",
        }
        response = self.client.post(self.file_url, data)
        # Should fail due to UniqueConstraint
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_file_isolation(self):
        p1 = Project.objects.create(user=self.user1, name="Proj1")
        p2 = Project.objects.create(user=self.user2, name="Proj2")
        ProjectFile.objects.create(project=p1, path="f1.txt")
        ProjectFile.objects.create(project=p2, path="f2.txt")

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.file_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["path"], "f1.txt")


class ProjectExportTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.project = Project.objects.create(user=self.user, name="Test Project")
        self.export_url = f"/api/sandbox/projects/{self.project.id}/export_zip/"

    def test_export_zip_unauthenticated(self):
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_zip_with_files(self):
        ProjectFile.objects.create(
            project=self.project, path="src/index.js", content="console.log('hello');"
        )
        ProjectFile.objects.create(
            project=self.project, path="src/style.css", content="body { margin: 0; }"
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("Test_Project-export.zip", response["Content-Disposition"])

        # Verify ZIP contents
        import io
        import zipfile
        buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            self.assertIn("src/index.js", names)
            self.assertIn("src/style.css", names)
            self.assertIn("README.md", names)

    def test_export_zip_empty_project(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")

    def test_export_zip_forbidden_for_other_user(self):
        other_user = User.objects.create_user(username="other", password="password")
        other_project = Project.objects.create(user=other_user, name="Other Project")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/sandbox/projects/{other_project.id}/export_zip/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_zip_sanitizes_paths(self):
        # Legitimate file that should be included
        ProjectFile.objects.create(project=self.project, path="..env", content="valid")
        # Malicious traversal files
        ProjectFile.objects.create(project=self.project, path="../evil.txt", content="evil")
        ProjectFile.objects.create(project=self.project, path="..\\evil.txt", content="evil")
        ProjectFile.objects.create(project=self.project, path="C:\\Windows\\win.ini", content="evil")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        import io
        import zipfile
        buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            # The valid file must be included
            self.assertIn("..env", names)
            # The malicious files must be excluded
            self.assertNotIn("../evil.txt", names)
            self.assertNotIn("..\\evil.txt", names)
            self.assertNotIn("C:\\Windows\\win.ini", names)
            self.assertNotIn("C:/Windows/win.ini", names)
