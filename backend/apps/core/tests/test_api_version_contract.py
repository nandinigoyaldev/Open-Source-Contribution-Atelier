"""Compatibility contracts for API version negotiation and retirement."""

import json

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.middleware.api_version import APIVersionMiddleware
from apps.core.versioning import parse_version_from_accept_header
from config.version_view import api_versions_view


class VersionContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = APIVersionMiddleware(lambda request: JsonResponse({"ok": True}))

    def call_api(self, accept=None):
        headers = {"HTTP_ACCEPT": accept} if accept is not None else {}
        return self.middleware(self.factory.get("/api/example/", **headers))

    def test_legacy_client_still_works(self):
        response = self.call_api()
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-API-Deprecation", response)
        self.assertIn("Accept", response["Vary"])

    def test_supported_and_malformed_explicit_versions(self):
        self.assertEqual(self.call_api("application/json; version=1.0").status_code, 200)
        for version in ("bogus", "", "1.0oops", "99.0"):
            with self.subTest(version=version):
                response = self.call_api(f"application/json; version={version}")
                self.assertEqual(response.status_code, 406)
                self.assertIn("Accept", response["Vary"])

    def test_quoted_header(self):
        self.assertEqual(parse_version_from_accept_header('application/json; version="v1.0"'), "1.0")

    @override_settings(DEPRECATED_API_VERSIONS={"1.0": {
        "deprecation": "@1700000000", "sunset": "Wed, 31 Dec 2099 23:59:59 GMT"
    }})
    def test_deprecated_version_before_sunset_keeps_working(self):
        response = self.call_api("application/json; version=1.0")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Deprecation"], "@1700000000")
        self.assertEqual(response["Sunset"], "Wed, 31 Dec 2099 23:59:59 GMT")

    @override_settings(DEPRECATED_API_VERSIONS={"1.0": {
        "deprecation": "@1700000000", "sunset": "Wed, 01 Jan 2020 00:00:00 GMT"
    }})
    def test_sunset_version_is_retired_without_calling_view(self):
        response = self.call_api("application/json; version=1.0")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response["Sunset"], "Wed, 01 Jan 2020 00:00:00 GMT")

    @override_settings(
        API_VERSION_DISCOVERY={"1.0": {"status": "stable"}},
        DEPRECATED_API_VERSIONS={"1.0": {"deprecation": "@1700000000", "sunset": "Wed, 31 Dec 2099 23:59:59 GMT"}},
    )
    def test_discovery_reports_same_lifecycle_as_response(self):
        response = self.call_api("application/json; version=1.0")
        discovery = json.loads(api_versions_view(self.factory.get("/api/versions/")).content)
        self.assertEqual(discovery["versions"][0]["deprecation"], response["Deprecation"])
        self.assertEqual(discovery["versions"][0]["sunset"], response["Sunset"])
