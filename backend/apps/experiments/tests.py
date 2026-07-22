from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class ExperimentsAPITests(APITestCase):
    def test_experiment_list_unauthorized(self):
        url = reverse("experiment-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_experimentassignment_list_unauthorized(self):
        url = reverse("experiment-assignment-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_experimentevent_list_unauthorized(self):
        url = reverse("experiment-event-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
