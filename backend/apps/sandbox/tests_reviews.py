import pytest
from django.contrib.auth import get_user_model

from apps.sandbox.models import CodeReviewComment, CodeReviewThread, CollabSession

User = get_user_model()


@pytest.mark.django_db
def test_code_review_models():
    import uuid

    user = User.objects.create(username="reviewer")
    session = CollabSession.objects.create(id=uuid.uuid4())

    thread = CodeReviewThread.objects.create(session=session, line_number=5)
    comment = CodeReviewComment.objects.create(
        thread=thread, user=user, content="LGTM!"
    )

    assert thread.line_number == 5
    assert not thread.is_resolved
    assert thread.comments.count() == 1
    assert thread.comments.first().content == "LGTM!"

    thread.is_resolved = True
    thread.save()
    assert thread.is_resolved


@pytest.mark.django_db
def test_code_review_edge_cases():
    import uuid

    user = User.objects.create(username="reviewer2")
    session = CollabSession.objects.create(id=uuid.uuid4())

    # 1. Thread without comments
    empty_thread = CodeReviewThread.objects.create(session=session, line_number=10)
    assert empty_thread.comments.count() == 0

    # 2. Deleting a session cascades to threads
    session.delete()
    assert CodeReviewThread.objects.filter(id=empty_thread.id).count() == 0


@pytest.mark.django_db
def test_collab_session_viewset(api_client, user):
    from rest_framework.test import APIClient
    from apps.sandbox.models import Project, CollabSession

    # Create project
    project = Project.objects.create(name="Test Project", user=user)

    # Force authenticate
    api_client.force_authenticate(user=user)

    # 1. Create session via POST
    response = api_client.post(
        "/api/sandbox/collab-sessions/", {"project": str(project.id)}
    )
    assert response.status_code == 201
    session_id = response.data["id"]

    # 2. Retrieve session
    response = api_client.get(f"/api/sandbox/collab-sessions/{session_id}/")
    assert response.status_code == 200

    # 3. Create another user to join the session
    another_user = User.objects.create_user(
        username="guest_user", password="guestpassword123"
    )
    guest_client = APIClient()
    guest_client.force_authenticate(user=another_user)

    # Guest joins session
    response = guest_client.post(f"/api/sandbox/collab-sessions/{session_id}/join/")
    assert response.status_code == 200
    assert another_user.id in response.data["allowed_users"]

    # Guest tries to destroy/end session (should fail)
    response = guest_client.delete(f"/api/sandbox/collab-sessions/{session_id}/")
    assert response.status_code == 403

    # Host destroys/ends session
    response = api_client.delete(f"/api/sandbox/collab-sessions/{session_id}/")
    assert response.status_code == 204
