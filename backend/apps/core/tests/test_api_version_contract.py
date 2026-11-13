"""Compatibility contracts for API version negotiation and retirement."""

import json
from unittest.mock import Mock

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.middleware.api_version import APIVersionMiddleware
from apps.core.versioning import (
    AcceptHeaderOrURLVersioning,
    parse_version_from_accept_header,
)
from config.version_view import api_versions_view


class VersionContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = APIVersionMiddleware(
            lambda request: JsonResponse({"ok": True})
        )

    def call_api(self, accept=None):
        headers = {"HTTP_ACCEPT": accept} if accept is not None else {}
        return self.middleware(self.factory.get("/api/example/", **headers))

    def test_legacy_client_still_works(self):
        response = self.call_api()
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-API-Deprecation", response)
        self.assertIn("Accept", response["Vary"])

    def test_supported_and_malformed_explicit_versions(self):
        self.assertEqual(
            self.call_api("application/json; version=1.0").status_code, 200
        )
        for version in (
            "bogus",
            "",
            "1.0oops",
            "99.0",
            '"1.0"oops',
            "1.0 garbage",
            '"1.0',
        ):
            with self.subTest(version=version):
                response = self.call_api(f"application/json; version={version}")
                self.assertEqual(response.status_code, 406)
                self.assertIn("Accept", response["Vary"])

    def test_quoted_header(self):
        self.assertEqual(
            parse_version_from_accept_header('application/json; version="v1.0"'), "1.0"
        )

    @override_settings(
        DEPRECATED_API_VERSIONS={
            "1.0": {
                "deprecation": "@1700000000",
                "sunset": "Wed, 31 Dec 2099 23:59:59 GMT",
            }
        }
    )
    def test_deprecated_version_before_sunset_keeps_working(self):
        response = self.call_api("application/json; version=1.0")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Deprecation"], "@1700000000")
        self.assertEqual(response["Sunset"], "Wed, 31 Dec 2099 23:59:59 GMT")

    @override_settings(
        DEPRECATED_API_VERSIONS={
            "1.0": {
                "deprecation": "@1700000000",
                "sunset": "Wed, 01 Jan 2020 00:00:00 GMT",
            }
        }
    )
    def test_sunset_version_is_retired_without_calling_view(self):
        view = Mock(return_value=JsonResponse({"ok": True}))
        middleware = APIVersionMiddleware(view)
        response = middleware(
            self.factory.get(
                "/api/example/", HTTP_ACCEPT="application/json; version=1.0"
            )
        )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response["Sunset"], "Wed, 01 Jan 2020 00:00:00 GMT")
        self.assertIn("Accept", response["Vary"])
        view.assert_not_called()

    def test_non_api_requests_are_unchanged(self):
        response = self.middleware(self.factory.get("/health/"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Vary", response)
        self.assertNotIn("X-API-Deprecation", response)

    def test_url_version_and_header_precedence(self):
        request = self.factory.get("/api/v1/example/")
        self.assertEqual(self.middleware(request).status_code, 200)
        self.assertEqual(request.version, "1.0")
        self.assertEqual(request.version_source, "url")
        request = self.factory.get(
            "/api/v1/example/", HTTP_ACCEPT="application/json; version=bogus"
        )
        self.assertEqual(self.middleware(request).status_code, 406)

    @override_settings(ALLOWED_API_VERSIONS=["1.0", "2.0"])
    def test_header_can_select_another_supported_version(self):
        request = self.factory.get(
            "/api/v1/example/", HTTP_ACCEPT="application/json; version=2"
        )
        self.assertEqual(self.middleware(request).status_code, 200)
        self.assertEqual(request.version, "2.0")
        self.assertEqual(request.version_source, "header")

    @override_settings(DEPRECATED_API_VERSIONS={"1.0": {"sunset": "invalid-date"}})
    def test_invalid_operator_date_does_not_retire_version(self):
        self.assertEqual(self.call_api().status_code, 200)

    def test_vary_preserves_existing_cache_dimensions(self):
        middleware = APIVersionMiddleware(
            lambda request: JsonResponse({"ok": True}, headers={"Vary": "Cookie"})
        )
        response = middleware(self.factory.get("/api/example/"))
        self.assertEqual(set(response["Vary"].split(", ")), {"Cookie", "Accept"})

    def test_drf_view_receives_version_string(self):
        class VersionView(APIView):
            authentication_classes = []
            permission_classes = []
            throttle_classes = []
            versioning_class = AcceptHeaderOrURLVersioning

            def get(self, request):
                return Response({"version": request.version})

        view = VersionView.as_view()
        for path, accept in (
            ("/api/example/", "application/json"),
            ("/api/v1/example/", "application/json"),
            ("/api/example/", "application/json; version=1"),
        ):
            with self.subTest(path=path, accept=accept):
                response = view(self.factory.get(path, HTTP_ACCEPT=accept))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["version"], "1.0")

        for version in ("", "bogus", '"1.0"garbage'):
            with self.subTest(version=version):
                response = view(
                    self.factory.get(
                        "/api/v1/example/",
                        HTTP_ACCEPT=f"application/json; version={version}",
                    )
                )
                self.assertEqual(response.status_code, 406)

    @override_settings(
        API_VERSION_DISCOVERY={"1.0": {"status": "stable"}},
        DEPRECATED_API_VERSIONS={
            "1.0": {
                "deprecation": "@1700000000",
                "sunset": "Wed, 31 Dec 2099 23:59:59 GMT",
            }
        },
    )
    def test_discovery_reports_same_lifecycle_as_response(self):
        response = self.call_api("application/json; version=1.0")
        discovery = json.loads(
            api_versions_view(self.factory.get("/api/versions/")).content
        )
        self.assertEqual(
            discovery["versions"][0]["deprecation"], response["Deprecation"]
        )
        self.assertEqual(discovery["versions"][0]["sunset"], response["Sunset"])
