from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class Issue_categorizationAPITests(APITestCase):
    def test_category_list_unauthorized(self):
        url = reverse('category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_issuecategoryassignment_list_unauthorized(self):
        url = reverse('issue-category-assignment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_issuetag_list_unauthorized(self):
        url = reverse('issue-tag-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_issuetagassignment_list_unauthorized(self):
        url = reverse('issue-tag-assignment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_categorysuggestion_list_unauthorized(self):
        url = reverse('category-suggestion-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

