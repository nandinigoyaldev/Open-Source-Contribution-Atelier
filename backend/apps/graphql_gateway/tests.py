"""
Tests for GraphQL federation gateway.
"""

from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model

User = get_user_model()
from django.urls import reverse
from rest_framework.test import APITestCase


class GraphQLGatewayTest(APITestCase):
    """
    Test GraphQL federation gateway.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.url = reverse("graphql_gateway:graphql_gateway")

    def test_gateway_health(self):
        """Test gateway health endpoint."""
        response = self.client.get(reverse("graphql_gateway:graphql_health"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())

    def test_unauthenticated_graphql_query(self):
        """Test GraphQL query returns 401 if unauthenticated."""
        query = "query { me { id } }"
        response = self.client.post(self.url, {"query": query}, format="json")
        self.assertEqual(response.status_code, 401)

    @patch("apps.graphql_gateway.gateway.requests.post")
    def test_graphql_query(self, mock_post):
        """Test GraphQL query execution."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "data": {"content": {"id": "1", "title": "Test"}}
        }

        self.client.force_authenticate(user=self.user)
        query = """
        query {
            content(id: "1") {
                id
                title
            }
        }
        """

        response = self.client.post(self.url, {"query": query}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_query_depth_limiting(self):
        """Test that extremely nested queries are blocked."""
        self.client.force_authenticate(user=self.user)
        # 11 levels of depth
        deep_query = "query { a { b { c { d { e { f { g { h { i { j { k { l } } } } } } } } } } } }"
        response = self.client.post(self.url, {"query": deep_query}, format="json")
        self.assertEqual(
            response.status_code, 200
        )  # DRF responds 200 with GraphQL error
        self.assertIn("errors", response.json())
        self.assertIn(
            "Query depth exceeds limit of 10", response.json()["errors"][0]["message"]
        )

    @patch("apps.graphql_gateway.gateway.requests.post")
    def test_circuit_breaker(self, mock_post):
        """Test circuit breaker opens after 5 failures."""
        self.client.force_authenticate(user=self.user)
        mock_post.side_effect = requests.exceptions.Timeout("Timeout error")

        query = "query { content { id } }"

        # Trigger 5 timeouts
        for _ in range(5):
            response = self.client.post(self.url, {"query": query}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertIn("errors", response.json())
            self.assertIn("timeout", response.json()["errors"][0]["message"].lower())

        # The 6th request should fail immediately due to open circuit
        response = self.client.post(self.url, {"query": query}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("errors", response.json())
        self.assertIn("circuit open", response.json()["errors"][0]["message"].lower())

    def test_service_discovery(self):
        """Test service discovery."""
        from apps.graphql_gateway.gateway import ServiceRegistry

        ServiceRegistry.register_service("test", "http://localhost:9999/graphql")
        service = ServiceRegistry.get_service("test")

        self.assertIsNotNone(service)
        self.assertEqual(service["url"], "http://localhost:9999/graphql")
