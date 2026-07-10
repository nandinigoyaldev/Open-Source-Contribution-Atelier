from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.security_middleware import ContentSecurityPolicyMiddleware


class SecurityHeadersTests(SimpleTestCase):
    """Verify the application's required response security headers."""

    def test_content_security_policy_header_is_present(self):
        response = self.client.get("/api/version/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy", response.headers)

        policy = response.headers["Content-Security-Policy"]

        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("base-uri 'self'", policy)

    def test_content_type_options_header_is_nosniff(self):
        response = self.client.get("/api/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["X-Content-Type-Options"],
            "nosniff",
        )

    def test_frame_options_header_is_deny(self):
        response = self.client.get("/api/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["X-Frame-Options"],
            "DENY",
        )

    @override_settings(
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=False,
    )
    def test_hsts_header_is_present_on_https_response(self):
        response = self.client.get(
            "/api/version/",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)

        hsts = response.headers["Strict-Transport-Security"]

        self.assertIn("max-age=31536000", hsts)
        self.assertIn("includeSubDomains", hsts)

    @override_settings(SECURE_HSTS_SECONDS=31536000)
    def test_hsts_header_is_not_sent_over_http(self):
        response = self.client.get(
            "/api/version/",
            secure=False,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "Strict-Transport-Security",
            response.headers,
        )

    def test_existing_csp_header_is_not_overwritten(self):
        custom_policy = "default-src 'none'"

        def view(request):
            response = HttpResponse("ok")
            response["Content-Security-Policy"] = custom_policy
            return response

        middleware = ContentSecurityPolicyMiddleware(view)

        request = RequestFactory().get("/test/")
        response = middleware(request)

        self.assertEqual(
            response.headers["Content-Security-Policy"],
            custom_policy,
        )
