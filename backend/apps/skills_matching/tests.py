from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class Skills_matchingAPITests(APITestCase):
    def test_contributorprofile_list_unauthorized(self):
        url = reverse('contributor-profile-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_skilltag_list_unauthorized(self):
        url = reverse('skill-tag-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_issueskilltag_list_unauthorized(self):
        url = reverse('issue-skill-tag-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_newcomerfriendlinessscore_list_unauthorized(self):
        url = reverse('newcomer-friendliness-score-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recommendation_list_unauthorized(self):
        url = reverse('recommendation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_skillgapanalysis_list_unauthorized(self):
        url = reverse('skill-gap-analysis-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

