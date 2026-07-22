from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class Advanced_searchAPITests(APITestCase):
    def test_searchembedding_list_unauthorized(self):
        url = reverse("search-embedding-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usersearchprofile_list_unauthorized(self):
        url = reverse("user-search-profile-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_searchanalytics_list_unauthorized(self):
        url = reverse("search-analytics-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
