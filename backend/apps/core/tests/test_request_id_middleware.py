import logging
import re
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from apps.core.logging_filters import RequestIdFilter
from apps.core.middleware.request_id import (
    MAX_REQUEST_ID_LENGTH,
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    clean_request_id,
    get_request_id,
)


def run(headers=None, view=None):
    """Run one request through the middleware and return (request, response)."""
    seen = {}

    def get_response(request):
        seen["request"] = request
        seen["in_request"] = get_request_id()
        return view(request) if view else HttpResponse("ok")

    request = RequestFactory().get("/", **(headers or {}))
    return seen, RequestIdMiddleware(get_response)(request)


class CleanRequestIdTests(SimpleTestCase):
    def test_accepts_typical_ids(self):
        for value in [
            str(uuid.uuid4()),
            uuid.uuid4().hex,
            "abc-123",
            "01HZX3K9Q2V7M5N8P4R6T0W1YB",  # ULID
            "trace:4bf92f3577b34da6a3ce929d0e0e4736",
            "svc.web_1-req.42",
            "a" * MAX_REQUEST_ID_LENGTH,
            "7",
        ]:
            self.assertEqual(clean_request_id(value), value, value)

    def test_rejects_unsafe_or_oversized_ids(self):
        for value in [
            "",
            None,
            123,
            b"abc",
            "a" * (MAX_REQUEST_ID_LENGTH + 1),
            "a" * 10_000,
            "has space",
            "line\nbreak",
            "crlf\r\nSet-Cookie: x=1",
            "tab\there",
            'quote"inside',
            "brace}{",
            "<script>alert(1)</script>",
            "'; DROP TABLE users;--",
            "../../etc/passwd",
            "-leading-dash",
            ".leading-dot",
            "uniécode",
            "trailing-newline\n",
            "null\x00byte",
        ]:
            self.assertIsNone(clean_request_id(value), repr(value))


class RequestIdMiddlewareTests(SimpleTestCase):
    def test_generates_a_uuid_when_the_client_sends_none(self):
        seen, response = run()
        value = response[REQUEST_ID_HEADER]
        self.assertEqual(str(uuid.UUID(value)), value)
        self.assertEqual(seen["request"].request_id, value)
        self.assertEqual(seen["in_request"], value)

    def test_keeps_a_safe_incoming_id(self):
        seen, response = run({"HTTP_X_REQUEST_ID": "client-req-42"})
        self.assertEqual(response[REQUEST_ID_HEADER], "client-req-42")
        self.assertEqual(seen["request"].request_id, "client-req-42")

    def test_replaces_every_unsafe_incoming_id_with_a_generated_one(self):
        for bad in [
            "x" * 200,
            "x" * 100_000,
            "bad id",
            "evil\r\nX-Injected: 1",
            '","user_id":"admin',
            "<img src=x onerror=alert(1)>",
        ]:
            seen, response = run({"HTTP_X_REQUEST_ID": bad})
            value = response[REQUEST_ID_HEADER]
            self.assertNotEqual(value, bad)
            self.assertEqual(str(uuid.UUID(value)), value, bad)
            self.assertEqual(seen["request"].request_id, value)
            self.assertNotIn("X-Injected", response)

    def test_an_id_at_the_length_limit_is_kept(self):
        value = "a" * MAX_REQUEST_ID_LENGTH
        _, response = run({"HTTP_X_REQUEST_ID": value})
        self.assertEqual(response[REQUEST_ID_HEADER], value)

    def test_each_request_gets_its_own_id(self):
        ids = {run()[1][REQUEST_ID_HEADER] for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_the_id_is_cleared_after_the_request(self):
        run({"HTTP_X_REQUEST_ID": "first"})
        self.assertIsNone(get_request_id())

    def test_the_id_is_cleared_when_the_view_raises(self):
        def boom(request):
            raise RuntimeError("view failed")

        with self.assertRaises(RuntimeError):
            run({"HTTP_X_REQUEST_ID": "leaky"}, view=boom)
        self.assertIsNone(get_request_id())

    def test_the_header_is_set_on_error_responses(self):
        for status in (400, 401, 403, 404, 429, 500):
            _, response = run(
                view=lambda request, status=status: HttpResponse(status=status)
            )
            self.assertEqual(response.status_code, status)
            self.assertTrue(response[REQUEST_ID_HEADER])

    def test_log_records_during_the_request_carry_the_same_id(self):
        captured = {}

        def view(request):
            record = logging.LogRecord(
                "apps.test", logging.ERROR, __file__, 1, "failed", (), None
            )
            RequestIdFilter().filter(record)
            captured["record_id"] = record.request_id
            return HttpResponse("ok")

        _, response = run({"HTTP_X_REQUEST_ID": "log-me-1"}, view=view)
        self.assertEqual(captured["record_id"], "log-me-1")
        self.assertEqual(response[REQUEST_ID_HEADER], "log-me-1")

    def test_a_log_line_shows_the_generated_id_not_the_rejected_one(self):
        captured = {}

        def view(request):
            record = logging.LogRecord(
                "apps.test", logging.ERROR, __file__, 1, "failed", (), None
            )
            RequestIdFilter().filter(record)
            captured["line"] = '{"request_id": "%s"}' % record.request_id
            return HttpResponse("ok")

        _, response = run({"HTTP_X_REQUEST_ID": 'x","user_id":"admin'}, view=view)
        self.assertNotIn("admin", captured["line"])
        self.assertIn(response[REQUEST_ID_HEADER], captured["line"])


class RequestIdThroughTheFullStackTests(TestCase):
    """The real middleware chain: every API response carries the header, errors included."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_a_404_has_a_generated_id(self):
        response = self.client.get("/api/this-route-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        value = response[REQUEST_ID_HEADER]
        self.assertEqual(str(uuid.UUID(value)), value)

    def test_an_unauthorised_request_echoes_a_safe_client_id(self):
        response = self.client.get("/api/auth/me/", HTTP_X_REQUEST_ID="web-7f3a")
        self.assertIn(response.status_code, (401, 403, 404))
        self.assertEqual(response[REQUEST_ID_HEADER], "web-7f3a")

    def test_an_oversized_client_id_is_replaced(self):
        response = self.client.get(
            "/api/this-route-does-not-exist/", HTTP_X_REQUEST_ID="z" * 500
        )
        self.assertNotIn("z" * 100, response[REQUEST_ID_HEADER])
        self.assertLessEqual(len(response[REQUEST_ID_HEADER]), MAX_REQUEST_ID_LENGTH)

    def test_the_browser_may_send_and_read_the_header_across_origins(self):
        self.assertIn(REQUEST_ID_HEADER, settings.CORS_EXPOSE_HEADERS)
        self.assertIn("x-request-id", [h.lower() for h in settings.CORS_ALLOW_HEADERS])
        # the defaults must still be there
        self.assertIn("authorization", [h.lower() for h in settings.CORS_ALLOW_HEADERS])

    def test_the_id_is_in_the_exposed_headers_of_a_cross_origin_response(self):
        origin = settings.CORS_ALLOWED_ORIGINS[0]
        response = self.client.get(
            "/api/this-route-does-not-exist/", HTTP_ORIGIN=origin
        )
        exposed = response.headers.get("Access-Control-Expose-Headers", "")
        self.assertTrue(
            re.search(r"x-request-id", exposed, re.I),
            f"Access-Control-Expose-Headers was {exposed!r}",
        )
