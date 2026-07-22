from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class Burnout_detectionAPITests(APITestCase):
    def test_contributoractivity_list_unauthorized(self):
        url = reverse('contributor-activity-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_burnoutsignal_list_unauthorized(self):
        url = reverse('burnout-signal-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_intervention_list_unauthorized(self):
        url = reverse('intervention-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_burnoutmetric_list_unauthorized(self):
        url = reverse('burnout-metric-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

