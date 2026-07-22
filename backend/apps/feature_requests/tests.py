from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class Feature_requestsAPITests(APITestCase):
    def test_featurerequest_list_unauthorized(self):
        url = reverse("feature-request-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vote_list_unauthorized(self):
        url = reverse("vote-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_list_unauthorized(self):
        url = reverse("comment-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_statushistory_list_unauthorized(self):
        url = reverse("status-history-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_roadmapmilestone_list_unauthorized(self):
        url = reverse("roadmap-milestone-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
