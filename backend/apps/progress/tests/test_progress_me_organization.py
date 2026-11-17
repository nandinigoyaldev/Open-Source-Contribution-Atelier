"""
POST /api/progress/me/ for members of an organization (issue #3344).

User.organization is organizations.Organization but Lesson.organization is
content.Organization, so filtering lessons by the user's organization raised
ValueError and the endpoint answered 500 for every organization member.
"""

import pytest
from django.core.cache import cache

from apps.content.models import Lesson
from apps.content.models import Organization as ContentOrganization
from apps.content.services.lesson_service import LessonService
from apps.progress.models import LessonProgress

URL = "/api/progress/me/"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _lesson(slug, organization=None):
    return Lesson.objects.create(
        slug=slug,
        title=slug,
        summary="fixture",
        content="fixture",
        difficulty="beginner",
        organization=organization,
    )


@pytest.fixture
def public_lesson(db):
    return _lesson("public-lesson")


@pytest.fixture
def org_a_lesson(db):
    # content.Organization is a separate table, matched to the user's
    # organizations.Organization by name.
    return _lesson(
        "org-a-lesson",
        ContentOrganization._default_manager.create(name="Org A", slug="org-a"),
    )


@pytest.fixture
def org_b_lesson(db):
    return _lesson(
        "org-b-lesson",
        ContentOrganization._default_manager.create(name="Org B", slug="org-b"),
    )


@pytest.mark.django_db
class TestMyProgressOrganizationMember:
    def test_member_can_save_progress_on_a_public_lesson(
        self, authed_client_a, user_a, org_a, public_lesson
    ):
        response = authed_client_a.post(
            URL, {"lesson_slug": public_lesson.slug, "score": 80}, format="json"
        )

        assert response.status_code == 201, response.content
        row = LessonProgress.objects.get(user=user_a, lesson=public_lesson)
        assert row.organization_id == org_a.id

    def test_member_can_save_progress_on_their_own_org_lesson(
        self, authed_client_a, user_a, org_a_lesson
    ):
        response = authed_client_a.post(
            URL, {"lesson_slug": org_a_lesson.slug}, format="json"
        )

        assert response.status_code == 201, response.content
        assert LessonProgress.objects.filter(user=user_a, lesson=org_a_lesson).exists()

    def test_member_gets_404_for_another_orgs_lesson(
        self, authed_client_a, user_a, org_b_lesson
    ):
        response = authed_client_a.post(
            URL, {"lesson_slug": org_b_lesson.slug}, format="json"
        )

        assert response.status_code == 404
        assert not LessonProgress.objects.filter(user=user_a).exists()

    def test_member_gets_404_for_unknown_lesson(self, authed_client_a):
        response = authed_client_a.post(URL, {"lesson_slug": "nope"}, format="json")

        assert response.status_code == 404

    def test_second_write_updates_the_same_row(
        self, authed_client_a, user_a, public_lesson
    ):
        first = authed_client_a.post(
            URL,
            {"lesson_slug": public_lesson.slug, "expected_version": 0},
            format="json",
        )
        second = authed_client_a.post(
            URL,
            {"lesson_slug": public_lesson.slug, "expected_version": 1},
            format="json",
        )

        assert first.status_code == 201, first.content
        assert second.status_code == 200, second.content
        assert LessonProgress.objects.filter(user=user_a).count() == 1


@pytest.mark.django_db
class TestMyProgressWithoutOrganization:
    """Behaviour for users with no organization is unchanged."""

    def test_public_lesson_still_works(
        self, api_client, django_user_model, public_lesson
    ):
        user = django_user_model.objects.create_user(
            username="solo", email="solo@example.com", password="pw123456"
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            URL, {"lesson_slug": public_lesson.slug}, format="json"
        )

        assert response.status_code == 201, response.content

    def test_org_lesson_is_still_hidden(
        self, api_client, django_user_model, org_a_lesson
    ):
        user = django_user_model.objects.create_user(
            username="solo2", email="solo2@example.com", password="pw123456"
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            URL, {"lesson_slug": org_a_lesson.slug}, format="json"
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestGetLessonBySlug:
    def test_matches_organization_by_name(self, org_a, org_b, org_a_lesson):
        assert (
            LessonService.get_lesson_by_slug(org_a_lesson.slug, org_a) == org_a_lesson
        )
        with pytest.raises(Lesson.DoesNotExist):
            LessonService.get_lesson_by_slug(org_a_lesson.slug, org_b)

    def test_public_lesson_is_visible_to_any_organization(self, org_a, public_lesson):
        assert (
            LessonService.get_lesson_by_slug(public_lesson.slug, org_a) == public_lesson
        )

    def test_no_organization_means_no_filter(self, org_a_lesson):
        assert LessonService.get_lesson_by_slug(org_a_lesson.slug) == org_a_lesson
