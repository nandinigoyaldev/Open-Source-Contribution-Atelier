import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.progress.models import CodeSubmission, PlagiarismReport
from apps.content.models import Exercise, Lesson

User = get_user_model()


@pytest.mark.django_db
def test_e2e_plagiarism_detection():
    client1 = APIClient()
    client2 = APIClient()

    user1 = User.objects.create(username="student1")
    user2 = User.objects.create(username="student2")

    client1.force_authenticate(user=user1)
    client2.force_authenticate(user=user2)

    lesson = Lesson.objects.create(title="Test Lesson", slug="test-lesson")
    exercise = Exercise.objects.create(title="Test Exercise", lesson=lesson)

    code1 = """
def solve():
    return 42
"""
    code2 = """
def solve():
    return 42
"""

    # User 1 submits code
    response1 = client1.post(
        "/api/progress/code-submissions/",
        {"title": "My Solution", "code_snippet": code1, "exercise": exercise.id},
    )
    assert response1.status_code == 201

    # User 2 submits same code
    response2 = client2.post(
        "/api/progress/code-submissions/",
        {"title": "My Solution 2", "code_snippet": code2, "exercise": exercise.id},
    )
    assert response2.status_code == 201

    sub2_id = response2.data["id"]

    # Trigger the task synchronously as part of the E2E flow
    from apps.progress.tasks import analyze_submission_plagiarism

    analyze_submission_plagiarism(sub2_id)

    # Verify report was generated
    reports = PlagiarismReport.objects.filter(submission_id=sub2_id)
    assert reports.count() == 1
    assert reports.first().is_flagged is True
