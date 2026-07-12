import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.sandbox.models import BulkReplaceOperation, Project, ProjectFile

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="testpassword")


@pytest.fixture
def project(user):
    return Project.objects.create(name="Test Project", user=user)


@pytest.fixture
def setup_files(project):
    f1 = ProjectFile.objects.create(
        project=project,
        path="src/main.py",
        content="def test():\n    print('hello world')",
    )
    f2 = ProjectFile.objects.create(
        project=project,
        path="src/utils.py",
        content="def log():\n    print('hello world')",
    )
    return [f1, f2]


@pytest.mark.django_db
def test_global_replace(api_client, user, project, setup_files):
    api_client.force_authenticate(user=user)
    url = reverse("project-replace", kwargs={"pk": project.id})

    # Empty query should fail
    response = api_client.post(url, {"query": "", "replacement": "test"})
    assert response.status_code == 400

    # Valid replace
    response = api_client.post(
        url, {"query": "hello world", "replacement": "hi universe"}
    )
    assert response.status_code == 200
    assert response.data["modified_count"] == 2

    for f in ProjectFile.objects.filter(project=project):
        assert "hi universe" in f.content
        assert "hello world" not in f.content

    # Check if BulkReplaceOperation was created
    op = BulkReplaceOperation.objects.filter(project=project).first()
    assert op is not None
    assert str(setup_files[0].id) in op.previous_state


@pytest.mark.django_db
def test_undo_replace(api_client, user, project, setup_files):
    api_client.force_authenticate(user=user)

    # Perform a replace first
    replace_url = reverse("project-replace", kwargs={"pk": project.id})
    api_client.post(replace_url, {"query": "hello world", "replacement": "hi universe"})

    # Now undo it
    undo_url = reverse("project-undo-replace", kwargs={"pk": project.id})
    response = api_client.post(undo_url)

    assert response.status_code == 200
    assert response.data["restored_count"] == 2

    for f in ProjectFile.objects.filter(project=project):
        assert "hello world" in f.content
        assert "hi universe" not in f.content

    # Check if operation was deleted
    assert BulkReplaceOperation.objects.filter(project=project).count() == 0

    # Undoing again should fail
    response = api_client.post(undo_url)
    assert response.status_code == 400
