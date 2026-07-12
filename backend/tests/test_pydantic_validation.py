from django.test import TestCase, Client
from django.urls import reverse
import json


class PydanticValidationTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_user_registration_validation(self):
        """Test user registration validation with Pydantic"""
        url = reverse("register")

        # Test invalid data
        invalid_data = {
            "username": "a",  # too short
            "email": "invalid-email",
            "password": "weak",
        }

        response = self.client.post(
            url, json.dumps(invalid_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

        # Test valid data
        valid_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "StrongP@ss123",
            "first_name": "Test",
        }

        response = self.client.post(
            url, json.dumps(valid_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_prediction_validation(self):
        """Test prediction validation with Pydantic"""
        url = reverse("predict")

        # Test invalid type
        invalid_data = {"text": "Hello world", "type": "invalid-type"}

        response = self.client.post(
            url, json.dumps(invalid_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        # Test valid data
        valid_data = {"text": "Hello world", "type": "message"}

        response = self.client.post(
            url, json.dumps(valid_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
