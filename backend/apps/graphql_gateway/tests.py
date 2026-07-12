"""
Tests for GraphQL federation gateway.
"""

from django.test import TestCase, Client
from django.urls import reverse


class GraphQLGatewayTest(TestCase):
    """
    Test GraphQL federation gateway.
    """

    def setUp(self):
        self.client = Client()

    def test_gateway_health(self):
        """Test gateway health endpoint."""
        response = self.client.get("/api/graphql/graphql/health/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())

    def test_graphql_query(self):
        """Test GraphQL query execution."""
        query = """
        query {
            content(id: "1") {
                id
                title
            }
        }
        """

        response = self.client.post(
            "/api/graphql/graphql/", {"query": query}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

    def test_graphql_mutation(self):
        """Test GraphQL mutation execution."""
        mutation = """
        mutation {
            updateProgress(input: {
                moduleId: "1",
                lessonId: "1",
                completed: true,
                score: 100
            }) {
                moduleId
                completed
                progress
            }
        }
        """

        response = self.client.post(
            "/api/graphql/graphql/",
            {"query": mutation},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

    def test_service_discovery(self):
        """Test service discovery."""
        from apps.graphql_gateway.gateway import ServiceRegistry

        ServiceRegistry.register_service("test", "http://localhost:9999/graphql")
        service = ServiceRegistry.get_service("test")

        self.assertIsNotNone(service)
        self.assertEqual(service["url"], "http://localhost:9999/graphql")
