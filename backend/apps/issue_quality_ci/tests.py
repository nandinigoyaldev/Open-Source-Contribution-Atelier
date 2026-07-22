from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class Issue_quality_ciAPITests(APITestCase):
    def test_issuequalityrecord_list_unauthorized(self):
        url = reverse("issue-quality-record-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_qualitymetric_list_unauthorized(self):
        url = reverse("quality-metric-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_qualitycomment_list_unauthorized(self):
        url = reverse("quality-comment-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_qualitytrend_list_unauthorized(self):
        url = reverse("quality-trend-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
