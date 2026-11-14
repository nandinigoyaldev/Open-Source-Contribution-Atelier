import uuid

from django.test import RequestFactory, TestCase
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.response import Response

from apps.accounts.exceptions import throttle_exception_handler
from apps.core.celery_signals import (
    add_request_id_to_task,
    cleanup_request_id_in_task,
    set_request_id_in_task,
)
from apps.core.middleware.request_id import (
    RequestIdMiddleware,
    _thread_locals,
    get_correlation_id,
    get_request_id,
)


class CorrelationIdTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_generated_correlation_id(self):
        def dummy_view(request):
            return Response({"status": "ok"})

        middleware = RequestIdMiddleware(dummy_view)
        request = self.rf.get("/api/test/")
        response = middleware(request)

        self.assertIn("X-Correlation-ID", response)
        self.assertIn("X-Request-ID", response)
        self.assertEqual(response["X-Correlation-ID"], response["X-Request-ID"])
        self.assertTrue(len(response["X-Correlation-ID"]) > 10)

    def test_incoming_correlation_id_propagated(self):
        incoming_id = "custom-corr-id-12345"

        def dummy_view(request):
            self.assertEqual(request.correlation_id, incoming_id)
            return Response({"status": "ok"})

        middleware = RequestIdMiddleware(dummy_view)
        request = self.rf.get("/api/test/", HTTP_X_CORRELATION_ID=incoming_id)
        response = middleware(request)

        self.assertEqual(response["X-Correlation-ID"], incoming_id)
        self.assertEqual(response["X-Request-ID"], incoming_id)

    def test_error_responses_include_correlation_id(self):
        corr_id = "error-corr-id-777"
        request = self.rf.get("/api/test/", HTTP_X_CORRELATION_ID=corr_id)
        request.correlation_id = corr_id
        request.request_id = corr_id

        # 1. Validation error
        val_exc = ValidationError({"email": ["Invalid email address"]})
        val_resp = throttle_exception_handler(val_exc, {"request": request})
        self.assertEqual(val_resp.status_code, 400)
        self.assertEqual(val_resp["X-Correlation-ID"], corr_id)
        self.assertEqual(val_resp.data["correlation_id"], corr_id)

        # 2. Authentication error
        auth_exc = AuthenticationFailed("Invalid credentials")
        auth_resp = throttle_exception_handler(auth_exc, {"request": request})
        self.assertEqual(auth_resp.status_code, 401)
        self.assertEqual(auth_resp["X-Correlation-ID"], corr_id)
        self.assertEqual(auth_resp.data["correlation_id"], corr_id)

        # 3. Unhandled 500 error
        raw_exc = RuntimeError("Database crashed unexpectedly")
        err_resp = throttle_exception_handler(raw_exc, {"request": request})
        self.assertEqual(err_resp.status_code, 500)
        self.assertEqual(err_resp["X-Correlation-ID"], corr_id)
        self.assertEqual(err_resp.data["correlation_id"], corr_id)
        # Message should contain safe reference without exposing stack trace
        self.assertIn("Ref: error-co", err_resp.data["message"])
        self.assertNotIn("Database crashed", err_resp.data["message"])

    def test_celery_task_correlation_id_propagation(self):
        test_corr_id = "task-corr-id-999"
        _thread_locals.correlation_id = test_corr_id
        _thread_locals.request_id = test_corr_id

        headers = {}
        add_request_id_to_task(headers=headers)
        self.assertEqual(headers.get("x-correlation-id"), test_corr_id)
        self.assertEqual(headers.get("correlation_id"), test_corr_id)

        # Worker receives task
        task = type("DummyTask", (), {"name": "test_celery_task"})()
        task.request = type("TaskRequest", (), {"headers": headers})()
        set_request_id_in_task("task-uuid-1", task)

        self.assertEqual(get_correlation_id(), test_corr_id)
        cleanup_request_id_in_task("task-uuid-1", task)
        self.assertIsNone(get_correlation_id())
