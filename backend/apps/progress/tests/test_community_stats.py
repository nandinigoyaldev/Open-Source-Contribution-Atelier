import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import UserProfile
from apps.content.models import Lesson
from apps.organizations.models import Organization
from apps.progress.models import HelpRequest, LessonProgress
from apps.progress.views import CommunityStatsView

User = get_user_model()


class TestCommunityStatsView(APITestCase):
    def setUp(self):
        # Create organizations
        self.org1 = Organization.objects.create(name="Community Org 1")
        self.org2 = Organization.objects.create(name="Community Org 2")

        # Create dummy lesson
        self.lesson = Lesson.objects.create(
            title="Test Lesson",
            slug="test-lesson-community-stats",
            content="Lesson content",
        )

        # Create users
        self.user_no_org = User.objects.create_user(
            username="anon_like_user",
            email="anon_like@example.com",
            password="password123",
        )

        self.user_org1 = User.objects.create_user(
            username="org1_member",
            email="org1_member@example.com",
            password="password123",
        )
        profile1 = UserProfile.objects.get(user=self.user_org1)
        profile1.organization = self.org1
        profile1.save()
        self.user_org1.refresh_from_db()

        self.user_org2 = User.objects.create_user(
            username="org2_member",
            email="org2_member@example.com",
            password="password123",
        )
        profile2 = UserProfile.objects.get(user=self.user_org2)
        profile2.organization = self.org2
        profile2.save()
        self.user_org2.refresh_from_db()

        # Create LessonProgress records
        # 2 completed lessons for Org 1
        LessonProgress.objects.create(
            user=self.user_org1,
            lesson=self.lesson,
            organization=self.org1,
            completed=True,
        )
        # 1 completed lesson for Org 2
        LessonProgress.objects.create(
            user=self.user_org2,
            lesson=self.lesson,
            organization=self.org2,
            completed=True,
        )

        # Create HelpRequest records
        # 3 open help requests for Org 1
        for i in range(3):
            HelpRequest.objects.create(
                user=self.user_org1,
                lesson=self.lesson,
                organization=self.org1,
                message=f"Org 1 help {i}",
                status=HelpRequest.Status.OPEN,
            )

        # 1 open help request for Org 2
        HelpRequest.objects.create(
            user=self.user_org2,
            lesson=self.lesson,
            organization=self.org2,
            message="Org 2 help 1",
            status=HelpRequest.Status.OPEN,
        )

        self.client = APIClient()

    def test_permission_classes_includes_allow_any(self):
        from rest_framework.permissions import AllowAny

        assert AllowAny in CommunityStatsView.permission_classes

    def test_anonymous_user_can_access_community_stats(self):
        """
        Unauthenticated requests to GET /api/progress/community-stats/
        must return HTTP 200 without raising AttributeError.
        """
        response = self.client.get("/api/progress/community-stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert "active_contributors" in data
        assert "merged_prs" in data
        assert "response_sla" in data
        assert "open_requests" in data

        # Total completed lessons across all orgs = 1 + 1 = 2 -> merged_prs = 300 + 2 = 302
        assert data["merged_prs"] == 302
        # Total open help requests = 3 + 1 = 4
        assert data["open_requests"] == 4

    def test_authenticated_user_without_org_gets_global_stats(self):
        self.client.force_authenticate(user=self.user_no_org)
        response = self.client.get("/api/progress/community-stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["merged_prs"] == 302
        assert data["open_requests"] == 4

    def test_authenticated_user_with_org_gets_org_scoped_stats(self):
        self.client.force_authenticate(user=self.user_org1)
        response = self.client.get("/api/progress/community-stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        # Org 1 has 1 completed lesson -> merged_prs = 300 + 1 = 301
        assert data["merged_prs"] == 301
        # Org 1 has 3 open requests
        assert data["open_requests"] == 3

    def test_authenticated_user_org2_scoped_stats(self):
        self.client.force_authenticate(user=self.user_org2)
        response = self.client.get("/api/progress/community-stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        # Org 2 has 1 completed lesson -> merged_prs = 300 + 1 = 301
        assert data["merged_prs"] == 301
        # Org 2 has 1 open request
        assert data["open_requests"] == 1
