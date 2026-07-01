import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.content.models import Exercise
from apps.progress.models import CodeSubmission, ExerciseAttempt, PeerReview


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def users(db):
    author = User.objects.create_user(
        username="author", email="author@example.com", password="password"
    )
    reviewer1 = User.objects.create_user(
        username="reviewer1", email="rev1@example.com", password="password"
    )
    reviewer2 = User.objects.create_user(
        username="reviewer2", email="rev2@example.com", password="password"
    )
    unassigned = User.objects.create_user(
        username="unassigned", email="un@example.com", password="password"
    )
    return author, reviewer1, reviewer2, unassigned


from apps.content.models import Exercise, Lesson


@pytest.fixture
def custom_exercise(db):
    lesson = Lesson.objects.create(
        slug="advanced-trees", title="Advanced Trees", category="general"
    )
    return Exercise.objects.create(
        lesson=lesson, title="Advanced Search Trees", prompt="Implement an AVL tree."
    )


@pytest.fixture
def setup_eligibility(db, users, custom_exercise):
    author, reviewer1, reviewer2, unassigned = users
    # Make reviewer1 and reviewer2 eligible by giving them correct attempts
    ExerciseAttempt.objects.create(
        user=reviewer1, exercise=custom_exercise, is_correct=True
    )
    ExerciseAttempt.objects.create(
        user=reviewer2, exercise=custom_exercise, is_correct=True
    )


@pytest.mark.django_db
def test_submission_assignment(api_client, users, custom_exercise, setup_eligibility):
    author, reviewer1, reviewer2, unassigned = users
    api_client.force_authenticate(user=author)
    url = reverse("code-submissions")
    response = api_client.post(
        url,
        {
            "title": "My AVL Tree",
            "code_snippet": "class AVLTree: pass",
            "exercise": custom_exercise.id,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    submission = CodeSubmission.objects.get(id=response.data["id"])
    assert submission.status == CodeSubmission.Status.PENDING_REVIEW

    assigned = list(submission.assigned_reviewers.values_list("id", flat=True))
    assert reviewer1.id in assigned
    assert reviewer2.id in assigned
    assert unassigned.id not in assigned
    assert author.id not in assigned
    assert len(assigned) == 2


@pytest.mark.django_db
def test_peer_review_consensus(api_client, users, custom_exercise, setup_eligibility):
    author, reviewer1, reviewer2, unassigned = users

    # 1. Author submits
    api_client.force_authenticate(user=author)
    sub_response = api_client.post(
        reverse("code-submissions"),
        {
            "title": "My AVL Tree",
            "code_snippet": "class AVLTree: pass",
            "exercise": custom_exercise.id,
        },
    )
    sub_id = sub_response.data["id"]

    # 2. Unassigned tries to review - should fail
    api_client.force_authenticate(user=unassigned)
    url = reverse("peer-reviews", kwargs={"submission_id": sub_id})
    resp_unassigned = api_client.post(
        url, {"feedback": "Looks good", "rating": 5, "is_approved": True}
    )
    assert resp_unassigned.status_code == status.HTTP_403_FORBIDDEN

    # 3. Author tries to review their own - should fail
    api_client.force_authenticate(user=author)
    resp_author = api_client.post(
        url, {"feedback": "LGTM", "rating": 5, "is_approved": True}
    )
    assert resp_author.status_code == status.HTTP_400_BAD_REQUEST

    # 4. Reviewer 1 approves
    api_client.force_authenticate(user=reviewer1)
    resp_r1 = api_client.post(
        url, {"feedback": "Good job", "rating": 5, "is_approved": True}
    )
    assert resp_r1.status_code == status.HTTP_201_CREATED

    # Status should still be PENDING_REVIEW because only 1 review
    submission = CodeSubmission.objects.get(id=sub_id)
    assert submission.status == CodeSubmission.Status.PENDING_REVIEW

    # 5. Reviewer 2 approves
    api_client.force_authenticate(user=reviewer2)
    resp_r2 = api_client.post(
        url, {"feedback": "Perfect", "rating": 5, "is_approved": True}
    )
    assert resp_r2.status_code == status.HTTP_201_CREATED

    # Status should be REVIEWED and exercise attempt created
    submission = CodeSubmission.objects.get(id=sub_id)
    assert submission.status == CodeSubmission.Status.REVIEWED

    assert ExerciseAttempt.objects.filter(
        user=author, exercise=custom_exercise, is_correct=True
    ).exists()


@pytest.mark.django_db
def test_peer_review_escalation(api_client, users, custom_exercise, setup_eligibility):
    author, reviewer1, reviewer2, _ = users

    api_client.force_authenticate(user=author)
    sub_response = api_client.post(
        reverse("code-submissions"),
        {
            "title": "Bad Tree",
            "code_snippet": "class Tree:",
            "exercise": custom_exercise.id,
        },
    )
    sub_id = sub_response.data["id"]
    url = reverse("peer-reviews", kwargs={"submission_id": sub_id})

    # R1 approves
    api_client.force_authenticate(user=reviewer1)
    api_client.post(url, {"feedback": "ok", "is_approved": True})

    # R2 rejects
    api_client.force_authenticate(user=reviewer2)
    api_client.post(url, {"feedback": "bad", "is_approved": False})

    submission = CodeSubmission.objects.get(id=sub_id)
    assert submission.status == CodeSubmission.Status.ESCALATED
