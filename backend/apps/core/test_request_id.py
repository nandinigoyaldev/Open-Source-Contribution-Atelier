from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from apps.core.middleware.request_id import RequestIdMiddleware, get_request_id


class RequestIdMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_generates_request_id(self):
        request = self.factory.get("/")

        def get_response(req):
            self.assertTrue(hasattr(req, "request_id"))
            self.assertIsNotNone(get_request_id())
            self.assertEqual(req.request_id, get_request_id())
            return HttpResponse("OK")

        middleware = RequestIdMiddleware(get_response)
        response = middleware(request)

        self.assertIn("X-Request-ID", response)
        self.assertEqual(response["X-Request-ID"], request.request_id)

    def test_middleware_uses_existing_request_id(self):
        request = self.factory.get("/", HTTP_X_REQUEST_ID="test-1234")

        def get_response(req):
            self.assertEqual(req.request_id, "test-1234")
            self.assertEqual(get_request_id(), "test-1234")
            return HttpResponse("OK")

        middleware = RequestIdMiddleware(get_response)
        response = middleware(request)

        self.assertEqual(response["X-Request-ID"], "test-1234")
