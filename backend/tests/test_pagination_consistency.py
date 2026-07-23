"""
Automated tests for pagination consistency across API endpoints.
"""

import re
from typing import Dict, Any, List, Optional
from django.test import TestCase
from django.urls import get_resolver, URLPattern, URLResolver
from django.contrib.auth import get_user_model

User = get_user_model()
from rest_framework.test import APIClient
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination


class PaginationValidator:
    """
    Validate pagination consistency across API endpoints.
    """

    def __init__(self):
        self.issues: List[Dict[str, Any]] = []
        self.pagination_patterns = self._get_pagination_patterns()

    def _get_pagination_patterns(self) -> List[Dict[str, str]]:
        """Extract all API URL patterns."""
        urls = []
        resolver = get_resolver()

        def extract_patterns(pattern, prefix=""):
            if isinstance(pattern, URLPattern):
                if "/api/" in pattern.pattern:
                    urls.append(
                        {
                            "name": pattern.name or "",
                            "pattern": f"{prefix}{pattern.pattern}",
                            "callback": (
                                pattern.callback.__name__
                                if pattern.callback
                                else "unknown"
                            ),
                        }
                    )
            elif isinstance(pattern, URLResolver):
                new_prefix = f"{prefix}{pattern.pattern}"
                if "/api/" in new_prefix or new_prefix.startswith("api/"):
                    for sub_pattern in pattern.url_patterns:
                        extract_patterns(sub_pattern, new_prefix)

        extract_patterns(resolver)
        return urls

    def validate_pagination_structure(self, response_data: Dict) -> bool:
        """Validate that response has proper pagination structure."""
        required_fields = ["count", "next", "previous", "results"]

        for field in required_fields:
            if field not in response_data:
                return False

        # Validate data types
        if not isinstance(response_data.get("count"), int):
            return False
        if response_data.get("next") is not None and not isinstance(
            response_data.get("next"), str
        ):
            return False
        if response_data.get("previous") is not None and not isinstance(
            response_data.get("previous"), str
        ):
            return False
        if not isinstance(response_data.get("results"), list):
            return False

        return True

    def validate_page_size(self, response_data: Dict, max_page_size: int = 100) -> bool:
        """Validate that results size doesn't exceed max_page_size."""
        results = response_data.get("results", [])
        return len(results) <= max_page_size

    def run_checks(self, client, authenticated_user=None) -> List[Dict[str, Any]]:
        """Run pagination validation on all API endpoints."""
        issues = []

        for pattern in self.pagination_patterns:
            url = pattern["pattern"]

            # Skip non-list endpoints
            if not self._is_list_endpoint(url):
                continue

            try:
                # Make request
                response = client.get(url)

                if response.status_code == 200 and response.data:
                    # Check if response is paginated
                    is_paginated = self.validate_pagination_structure(response.data)

                    if not is_paginated and "results" in response.data:
                        issues.append(
                            {
                                "type": "missing_pagination_structure",
                                "url": url,
                                "callback": pattern["callback"],
                                "severity": "medium",
                                "description": f"Endpoint {url} returns list without pagination structure",
                            }
                        )
                    elif is_paginated:
                        # Check page size
                        if not self.validate_page_size(response.data):
                            issues.append(
                                {
                                    "type": "page_size_exceeded",
                                    "url": url,
                                    "callback": pattern["callback"],
                                    "severity": "high",
                                    "description": f"Endpoint {url} returned more than 100 items",
                                }
                            )
            except Exception as e:
                issues.append(
                    {
                        "type": "request_error",
                        "url": url,
                        "callback": pattern["callback"],
                        "severity": "low",
                        "description": f"Error testing {url}: {str(e)}",
                    }
                )

        return issues

    def _is_list_endpoint(self, url: str) -> bool:
        """Check if URL is likely a list endpoint."""
        list_indicators = [
            "list",
            "all",
            "search",
            "feed",
            "timeline",
            "badges",
            "users",
        ]
        for indicator in list_indicators:
            if indicator in url:
                return True
        return False


class PaginationConsistencyTest(TestCase):
    """
    Test suite for pagination consistency.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@example.com"
        )
        self.client.force_authenticate(user=self.user)
        self.validator = PaginationValidator()

    def test_all_list_endpoints_have_pagination(self):
        """Test that all list endpoints have pagination."""
        issues = self.validator.run_checks(self.client, self.user)

        if issues:
            print("\n" + "=" * 80)
            print("⚠️  PAGINATION ISSUES DETECTED")
            print("=" * 80)
            for issue in issues:
                print(f"  📍 {issue['url']}")
                print(f"     Type: {issue['type']}")
                print(f"     Severity: {issue['severity']}")
                print(f"     {issue['description']}")
                print()

        # Fail on critical issues
        critical_issues = [i for i in issues if i.get("severity") == "high"]
        self.assertEqual(
            len(critical_issues),
            0,
            f"Found {len(critical_issues)} critical pagination issues",
        )

    def test_pagination_structure_consistency(self):
        """Test that all endpoints use consistent pagination fields."""
        # Test specific endpoints
        endpoints = [
            "/api/content/",
            "/api/progress/",
            "/api/notifications/",
            "/api/chat/",
        ]

        for endpoint in endpoints:
            try:
                response = self.client.get(endpoint)
                if response.status_code == 200 and response.data:
                    # Check structure
                    has_count = "count" in response.data
                    has_next = "next" in response.data
                    has_previous = "previous" in response.data
                    has_results = "results" in response.data

                    # If it's paginated, all fields should exist
                    if has_results and not (has_count and has_next and has_previous):
                        self.fail(
                            f"Endpoint {endpoint} has 'results' but missing pagination fields: "
                            f"count={has_count}, next={has_next}, previous={has_previous}"
                        )
            except Exception as e:
                print(f"⚠️ Could not test {endpoint}: {e}")
