from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class Issue_routingAPITests(APITestCase):
    def test_expertisedomain_list_unauthorized(self):
        url = reverse('expertise-domain-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_maintainerexpertise_list_unauthorized(self):
        url = reverse('maintainer-expertise-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_issuerouting_list_unauthorized(self):
        url = reverse('issue-routing-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_routingmetric_list_unauthorized(self):
        url = reverse('routing-metric-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

