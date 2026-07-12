from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from .models import Organization

class OrganizationViewSetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.org = Organization.objects.create(name="Test Org", description="Test Desc")
        self.url = "/api/organizations/"

    def test_list_organizations_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_organizations_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Using pagination might change the response shape, but ViewSet defaults to list if no pagination is configured for the view
        # We can safely test for results array if pagination is on, otherwise it's just a list
        if "results" in response.data:
            self.assertEqual(len(response.data["results"]), 1)
        else:
            self.assertEqual(len(response.data), 1)

    def test_create_organization(self):
        self.client.force_authenticate(user=self.user)
        data = {"name": "New Org", "description": "New Desc"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Organization.objects.count(), 2)
