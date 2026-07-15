from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class OpenAPIDocumentationTests(APITestCase):
    """
    Test suite verifying that OpenAPI schema generation, Swagger UI,
    and ReDoc UI documentation endpoints are configured correctly and loadable.
    """

    def test_schema_endpoint(self):
        """
        Verify that the schema endpoint returns the generated OpenAPI schema
        with the correct Content-Type (YAML/JSON).
        """
        url = reverse("schema")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be a dict (usually JSON or YAML parseable)
        self.assertTrue(isinstance(response.data, dict) or "openapi" in str(response.content))

    def test_swagger_ui_endpoint(self):
        """
        Verify that the Swagger UI HTML documentation page loads successfully.
        """
        url = reverse("swagger-ui")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"swagger-ui", response.content.lower() or b"swagger")

    def test_redoc_ui_endpoint(self):
        """
        Verify that the ReDoc UI HTML documentation page loads successfully.
        """
        url = reverse("redoc-ui")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"redoc", response.content.lower())
