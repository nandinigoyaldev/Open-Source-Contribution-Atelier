from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class OnboardingAPITests(APITestCase):
    def test_onboardingjourney_list_unauthorized(self):
        url = reverse("onboarding-journey-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_journeyevent_list_unauthorized(self):
        url = reverse("journey-event-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_onboardingnudge_list_unauthorized(self):
        url = reverse("onboarding-nudge-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_onboardingmetric_list_unauthorized(self):
        url = reverse("onboarding-metric-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
