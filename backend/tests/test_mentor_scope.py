"""
Tests for mentor scope permissions.

Verifies that the GET /api/progress/mentor/help-requests/ endpoint:
  - Returns only HelpRequest tickets whose lesson is in the mentor's assigned scope.
  - Rejects requests from authenticated users who are not mentors (403).
  - Rejects unauthenticated requests (401).
  - Returns an empty list when a mentor has no assigned lessons.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.models import MentorProfile
from apps.content.models import Lesson
from apps.progress.models import HelpRequest

MENTOR_ENDPOINT = "/api/progress/mentor/help-requests/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lesson(slug: str, title: str | None = None, order: int = 0) -> Lesson:
    return Lesson.objects.create(
        title=title or slug.replace("-", " ").title(),
        slug=slug,
        summary="summary",
        content="content",
        order=order,
    )


def _make_help_request(user: User, lesson: Lesson, message: str = "Help!") -> HelpRequest:
    return HelpRequest.objects.create(user=user, lesson=lesson, message=message)


def _make_mentor(username: str, lessons: list[Lesson] | None = None) -> User:
    user = User.objects.create_user(username=username, password="strongpass123")
    profile = MentorProfile.objects.create(user=user)
    if lessons:
        profile.assigned_lessons.set(lessons)
    return user


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mentor_can_see_assigned_lesson_tickets():
    """Mentor receives only the tickets for their assigned lessons."""
    learner = User.objects.create_user(username="learner1", password="strongpass123")
    lesson_a = _make_lesson("git-basics", order=1)
    lesson_b = _make_lesson("git-branching", order=2)

    mentor = _make_mentor("mentor_alice", lessons=[lesson_a])

    ticket_a = _make_help_request(learner, lesson_a, message="Stuck on git basics")
    _make_help_request(learner, lesson_b, message="Stuck on branching")  # out of scope

    client = APIClient()
    client.force_authenticate(user=mentor)

    response = client.get(MENTOR_ENDPOINT)

    assert response.status_code == 200
    ids = [item["id"] for item in response.data]
    assert ticket_a.id in ids
    # Out-of-scope ticket must not appear
    assert len(ids) == 1


@pytest.mark.django_db
def test_mentor_sees_tickets_across_all_assigned_lessons():
    """When a mentor has multiple assigned lessons, tickets from all appear."""
    learner = User.objects.create_user(username="learner2", password="strongpass123")
    lesson_a = _make_lesson("git-basics-2", order=1)
    lesson_b = _make_lesson("git-branching-2", order=2)
    lesson_c = _make_lesson("git-merging", order=3)

    mentor = _make_mentor("mentor_bob", lessons=[lesson_a, lesson_b])

    ticket_a = _make_help_request(learner, lesson_a, message="A")
    ticket_b = _make_help_request(learner, lesson_b, message="B")
    _make_help_request(learner, lesson_c, message="C")  # lesson_c not assigned

    client = APIClient()
    client.force_authenticate(user=mentor)

    response = client.get(MENTOR_ENDPOINT)

    assert response.status_code == 200
    ids = {item["id"] for item in response.data}
    assert ticket_a.id in ids
    assert ticket_b.id in ids
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# Scope boundary — mentor cannot cross into another mentor's modules
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mentor_cannot_see_unassigned_lesson_tickets():
    """A mentor sees zero tickets when none belong to their assigned lessons."""
    learner = User.objects.create_user(username="learner3", password="strongpass123")
    lesson_x = _make_lesson("git-rebase", order=1)
    lesson_y = _make_lesson("git-cherry-pick", order=2)

    mentor = _make_mentor("mentor_carol", lessons=[lesson_y])
    _make_help_request(learner, lesson_x, message="Stuck on rebase")

    client = APIClient()
    client.force_authenticate(user=mentor)

    response = client.get(MENTOR_ENDPOINT)

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_two_mentors_see_independent_scopes():
    """Two mentors with different assigned lessons each see only their own tickets."""
    learner = User.objects.create_user(username="learner4", password="strongpass123")
    lesson_a = _make_lesson("git-init", order=1)
    lesson_b = _make_lesson("git-add", order=2)

    mentor1 = _make_mentor("mentor_dan", lessons=[lesson_a])
    mentor2 = _make_mentor("mentor_eve", lessons=[lesson_b])

    ticket_a = _make_help_request(learner, lesson_a, message="init help")
    ticket_b = _make_help_request(learner, lesson_b, message="add help")

    client = APIClient()

    client.force_authenticate(user=mentor1)
    resp1 = client.get(MENTOR_ENDPOINT)
    assert resp1.status_code == 200
    assert [item["id"] for item in resp1.data] == [ticket_a.id]

    client.force_authenticate(user=mentor2)
    resp2 = client.get(MENTOR_ENDPOINT)
    assert resp2.status_code == 200
    assert [item["id"] for item in resp2.data] == [ticket_b.id]


# ---------------------------------------------------------------------------
# Permission denial
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_unauthenticated_request_is_rejected():
    """Anonymous requests receive HTTP 401."""
    client = APIClient()
    response = client.get(MENTOR_ENDPOINT)
    assert response.status_code == 401


@pytest.mark.django_db
def test_non_mentor_authenticated_user_is_forbidden():
    """Authenticated users without a MentorProfile receive HTTP 403."""
    regular_user = User.objects.create_user(username="learner5", password="strongpass123")
    client = APIClient()
    client.force_authenticate(user=regular_user)

    response = client.get(MENTOR_ENDPOINT)

    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_user_without_mentor_profile_is_forbidden():
    """
    is_staff alone does not grant mentor access; a MentorProfile is required.
    This guards against accidental scope escalation for admins.
    """
    admin = User.objects.create_user(username="admin_no_profile", password="strongpass123", is_staff=True)
    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.get(MENTOR_ENDPOINT)

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Edge case — mentor assigned no lessons
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mentor_with_no_assigned_lessons_sees_empty_list():
    """A MentorProfile with an empty assigned_lessons set returns [] not an error."""
    learner = User.objects.create_user(username="learner6", password="strongpass123")
    lesson = _make_lesson("git-stash", order=1)
    _make_help_request(learner, lesson, message="stash help")

    # Mentor exists but has no lessons assigned yet
    mentor = _make_mentor("mentor_frank", lessons=[])

    client = APIClient()
    client.force_authenticate(user=mentor)

    response = client.get(MENTOR_ENDPOINT)

    assert response.status_code == 200
    assert response.data == []
