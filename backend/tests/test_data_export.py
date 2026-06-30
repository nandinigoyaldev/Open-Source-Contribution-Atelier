import csv
import io
import json
import zipfile

import pytest
from apps.content.models import Lesson
from apps.progress.models import LessonProgress
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="exportuser", email="export@example.com", password="TestPassword123!"
    )


@pytest.fixture
def other_user():
    return User.objects.create_user(
        username="other", email="other@example.com", password="test"
    )


@pytest.mark.django_db
class TestDataExport:
    def test_json_export_success(self, client, user, other_user):
        client.force_authenticate(user=user)

        # Create some data for user
        lesson = Lesson.objects.create(slug="test-lesson", title="Test")
        LessonProgress.objects.create(user=user, lesson=lesson, score=100)

        # Create data for other_user
        LessonProgress.objects.create(user=other_user, lesson=lesson, score=50)

        response = client.get("/api/users/me/export/?export_format=json")
        print(response.content)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        assert (
            'attachment; filename="data_export_exportuser.json"'
            in response["Content-Disposition"]
        )

        data = json.loads(response.content)
        assert "user_profile" in data
        assert data["user_profile"][0]["username"] == "exportuser"

        assert "lesson_progress" in data
        assert len(data["lesson_progress"]) == 1
        assert data["lesson_progress"][0]["score"] == 100

        # Ensure other user's data isn't included
        for lp in data["lesson_progress"]:
            assert lp.get("score") != 50

    def test_csv_export_success(self, client, user):
        client.force_authenticate(user=user)

        lesson = Lesson.objects.create(slug="test-lesson-csv", title="CSV Test")
        LessonProgress.objects.create(user=user, lesson=lesson, score=99)

        response = client.get("/api/users/me/export/?export_format=csv")
        print(response.content)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"

        # Read the zip file
        z = zipfile.ZipFile(io.BytesIO(response.content))
        file_list = z.namelist()

        assert "user_profile.csv" in file_list
        assert "lesson_progress.csv" in file_list

        # Check CSV content
        with z.open("lesson_progress.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, "utf-8"))
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["score"] == "99"

    def test_unsupported_format(self, client, user):
        client.force_authenticate(user=user)
        response = client.get("/api/users/me/export/?export_format=xml")
        assert response.status_code == 400

    def test_unauthenticated_request(self, client):
        response = client.get("/api/users/me/export/?export_format=json")
        assert response.status_code == 401

    def test_empty_dataset(self, client, user):
        client.force_authenticate(user=user)
        response = client.get("/api/users/me/export/?export_format=json")
        print(response.content)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert len(data["lesson_progress"]) == 0
        assert len(data["user_profile"]) == 1
