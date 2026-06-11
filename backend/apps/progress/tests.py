from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from .models import Certificate

class CertificateVerificationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.certificate = Certificate.objects.create(
            user=self.user,
            course_name="Test Course"
        )
        self.url = reverse('verify-certificate', kwargs={'hash': self.certificate.verification_hash})
        self.invalid_url = reverse('verify-certificate', kwargs={'hash': 'invalid-hash-123'})

    def test_verify_valid_certificate(self):
        """Test that a valid hash returns the correct public certificate data."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_valid'])
        self.assertEqual(response.data['certificate']['learner_name'], 'testuser')
        self.assertEqual(response.data['certificate']['course_name'], 'Test Course')
        self.assertEqual(response.data['certificate']['verification_hash'], str(self.certificate.verification_hash))

    def test_verify_invalid_certificate(self):
        """Test that an invalid or fake hash returns a 404 Not Found."""
        response = self.client.get(self.invalid_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
