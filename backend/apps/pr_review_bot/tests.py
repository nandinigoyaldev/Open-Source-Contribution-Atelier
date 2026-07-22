from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class Pr_review_botAPITests(APITestCase):
    def test_prreview_list_unauthorized(self):
        url = reverse('pr-review-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_codeissue_list_unauthorized(self):
        url = reverse('code-issue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_prreviewcomment_list_unauthorized(self):
        url = reverse('pr-review-comment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reviewconfig_list_unauthorized(self):
        url = reverse('review-config-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

