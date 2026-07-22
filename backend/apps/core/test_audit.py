import json
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()
from django.contrib.contenttypes.models import ContentType
from apps.core.models import AdminAuditLog
from apps.core.middleware import AdminAuditMiddleware, _audit_local
from apps.core.utils import log_action
from django.http import HttpResponse


class AuditLogTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )

    def test_middleware_captures_admin_request(self):
        request = self.factory.get("/admin/some-page/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        def dummy_view(req):
            self.assertEqual(_audit_local.actor, self.user)
            self.assertEqual(_audit_local.ip_address, "192.168.1.1")
            return HttpResponse("OK")

        middleware = AdminAuditMiddleware(dummy_view)
        middleware(request)

        # Ensures thread locals are cleaned up
        self.assertIsNone(getattr(_audit_local, "actor", None))

    def test_log_action_decorator(self):
        @log_action("custom_action", lambda r: {"foo": "bar"})
        def dummy_view(request):
            return HttpResponse("OK")

        request = self.factory.get("/admin/custom/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        middleware = AdminAuditMiddleware(dummy_view)
        middleware(request)

        log = AdminAuditLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.action, "custom_action")
        self.assertEqual(log.details, {"foo": "bar"})

    def test_signal_logging(self):
        request = self.factory.get("/admin/test/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        def test_view(req):
            # Create a user to trigger post_save
            # User model is registered in admin by default
            User.objects.create_user("testuser", "test@example.com", "password")
            return HttpResponse("OK")

        middleware = AdminAuditMiddleware(test_view)
        middleware(request)

        logs = AdminAuditLog.objects.filter(action="user_created")
        self.assertEqual(logs.count(), 1)

        log = logs.first()
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.ip_address, "10.0.0.1")
