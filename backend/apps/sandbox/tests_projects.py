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
