import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import UserProfile
from apps.challenges.models import Challenge
from apps.organizations.models import Organization

User = get_user_model()


class TestChallengeViewSetPermissionsAndQueryset(APITestCase):
    def setUp(self):
        # Create organizations
        self.org1 = Organization.objects.create(name="Org One")
        self.org2 = Organization.objects.create(name="Org Two")

        # Create users
        self.user_no_org = User.objects.create_user(
            username="no_org_user",
            email="no_org@example.com",
            password="password123",
        )

        self.user_org1 = User.objects.create_user(
            username="org1_user",
            email="org1@example.com",
            password="password123",
        )
        profile1 = UserProfile.objects.get(user=self.user_org1)
        profile1.organization = self.org1
        profile1.save()
        self.user_org1.refresh_from_db()

        self.user_org2 = User.objects.create_user(
            username="org2_user",
            email="org2@example.com",
            password="password123",
        )
        profile2 = UserProfile.objects.get(user=self.user_org2)
        profile2.organization = self.org2
        profile2.save()
        self.user_org2.refresh_from_db()

        # Create challenges
        # 1. Global Public Challenge (no org, is_public=True)
        self.public_challenge_global = Challenge.objects.create(
            title="Global Public Challenge",
            slug="global-public",
            summary="Public for everyone",
            difficulty="beginner",
            points=50,
            organization=None,
            is_public=True,
        )

        # 2. Org1 Public Challenge (org1, is_public=True)
        self.public_challenge_org1 = Challenge.objects.create(
            title="Org 1 Public Challenge",
            slug="org1-public",
            summary="Org 1 public challenge",
            difficulty="intermediate",
            points=100,
            organization=self.org1,
            is_public=True,
        )

        # 3. Org1 Private Challenge (org1, is_public=False)
        self.private_challenge_org1 = Challenge.objects.create(
            title="Org 1 Private Challenge",
            slug="org1-private",
            summary="Org 1 internal challenge",
            difficulty="advanced",
            points=150,
            organization=self.org1,
            is_public=False,
        )

        # 4. Org2 Private Challenge (org2, is_public=False)
        self.private_challenge_org2 = Challenge.objects.create(
            title="Org 2 Private Challenge",
            slug="org2-private",
            summary="Org 2 internal challenge",
            difficulty="advanced",
            points=150,
            organization=self.org2,
            is_public=False,
        )

        # 5. Non-Public Null-Org Challenge (organization=None, is_public=False)
        self.private_challenge_null_org = Challenge.objects.create(
            title="Null Org Private Challenge",
            slug="null-org-private",
            summary="Private challenge with no org assigned",
            difficulty="intermediate",
            points=75,
            organization=None,
            is_public=False,
        )

        self.client = APIClient()

    # -------------------------------------------------------------------
    # Task 1 & Bug 1: Anonymous User Scenarios
    # -------------------------------------------------------------------
    def test_anonymous_user_can_list_challenges_without_crash(self):
        """
        Unauthenticated requests to GET /api/challenges/ must return HTTP 200
        without throwing an AttributeError on AnonymousUser.
        """
        response = self.client.get("/api/challenges/")
        assert response.status_code == status.HTTP_200_OK

        results = (
            response.data
            if isinstance(response.data, list)
            else response.data.get("results", [])
        )
        slugs = [c["slug"] for c in results]

        # Anonymous user should see public challenges
        assert "global-public" in slugs
        assert "org1-public" in slugs

        # Anonymous user must NOT see private challenges
        assert "org1-private" not in slugs
        assert "org2-private" not in slugs
        assert "null-org-private" not in slugs

    def test_anonymous_user_can_retrieve_public_challenge(self):
        response = self.client.get(
            f"/api/challenges/{self.public_challenge_global.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == "global-public"

    def test_anonymous_user_cannot_retrieve_private_challenge(self):
        response = self.client.get(f"/api/challenges/{self.private_challenge_org1.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # -------------------------------------------------------------------
    # Task 2 & Bug 2: Authenticated User Without Organization
    # -------------------------------------------------------------------
    def test_authenticated_user_without_org_sees_only_public_challenges(self):
        """
        Authenticated user with organization=None must see public challenges
        and MUST NOT see private challenges (fixes organization=None data leak).
        """
        self.client.force_authenticate(user=self.user_no_org)
        response = self.client.get("/api/challenges/")
        assert response.status_code == status.HTTP_200_OK

        results = (
            response.data
            if isinstance(response.data, list)
            else response.data.get("results", [])
        )
        slugs = [c["slug"] for c in results]

        assert "global-public" in slugs
        assert "org1-public" in slugs
        assert "org1-private" not in slugs
        assert "org2-private" not in slugs
        assert "null-org-private" not in slugs

    # -------------------------------------------------------------------
    # Authenticated User With Organization
    # -------------------------------------------------------------------
    def test_authenticated_user_with_org_sees_public_and_their_org_private_challenges(
        self,
    ):
        """
        User belonging to Org 1 should see:
        - All public challenges
        - Private challenges belonging to Org 1
        User must NOT see private challenges belonging to Org 2 or unassigned private challenges.
        """
        self.client.force_authenticate(user=self.user_org1)
        response = self.client.get("/api/challenges/")
        assert response.status_code == status.HTTP_200_OK

        results = (
            response.data
            if isinstance(response.data, list)
            else response.data.get("results", [])
        )
        slugs = [c["slug"] for c in results]

        assert "global-public" in slugs
        assert "org1-public" in slugs
        assert "org1-private" in slugs  # User's own org private challenge

        # Must NOT see other org's private challenge or null-org private challenge
        assert "org2-private" not in slugs
        assert "null-org-private" not in slugs

    def test_authenticated_user_org2_isolation(self):
        self.client.force_authenticate(user=self.user_org2)
        response = self.client.get("/api/challenges/")
        assert response.status_code == status.HTTP_200_OK

        results = (
            response.data
            if isinstance(response.data, list)
            else response.data.get("results", [])
        )
        slugs = [c["slug"] for c in results]

        assert "global-public" in slugs
        assert "org1-public" in slugs
        assert "org2-private" in slugs  # User's own org private challenge

        assert "org1-private" not in slugs
        assert "null-org-private" not in slugs

    def test_org1_user_can_retrieve_their_org_private_challenge(self):
        self.client.force_authenticate(user=self.user_org1)
        response = self.client.get(f"/api/challenges/{self.private_challenge_org1.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == "org1-private"

    def test_org1_user_cannot_retrieve_other_org_private_challenge(self):
        self.client.force_authenticate(user=self.user_org1)
        response = self.client.get(f"/api/challenges/{self.private_challenge_org2.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # -------------------------------------------------------------------
    # Task 4: Explicit permission_classes verification
    # -------------------------------------------------------------------
    def test_challenge_viewset_permission_classes(self):
        from apps.challenges.views import ChallengeViewSet
        from rest_framework.permissions import AllowAny

        assert AllowAny in ChallengeViewSet.permission_classes
