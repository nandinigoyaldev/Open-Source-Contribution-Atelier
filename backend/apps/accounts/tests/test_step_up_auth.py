import time
from unittest import mock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.accounts.models import UserSession
from apps.accounts.permissions import (
    IsRecentAuthentication,
    StepUpAuthMiddleware,
    generate_step_up_token,
    is_recently_authenticated,
    require_recent_authentication,
    verify_step_up_token,
)
from apps.accounts.totp import generate_totp_secret, verify_totp_code

User = get_user_model()


class DummyProtectedView(APIView):
    permission_classes = [IsRecentAuthentication]

    def post(self, request):
        return Response({"status": "sensitive_action_completed"})


class DummyDecoratedView(APIView):
    @require_recent_authentication(max_age_seconds=300)
    def post(self, request):
        return Response({"status": "decorated_action_completed"})


class StepUpAuthenticationUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="stepup_user",
            email="stepup@example.com",
            password="StrongPassword123!",
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other@example.com",
            password="StrongPassword123!",
        )
        self.factory = APIRequestFactory()

    def test_token_generation_and_verification(self):
        token = generate_step_up_token(self.user, max_age_seconds=300)
        self.assertTrue(verify_step_up_token(token, self.user, max_age_seconds=300))
        # Wrong user must fail
        self.assertFalse(verify_step_up_token(token, self.other_user, max_age_seconds=300))
        # Empty or invalid token
        self.assertFalse(verify_step_up_token("invalid.token.here", self.user, max_age_seconds=300))

    def test_token_expiration(self):
        token = generate_step_up_token(self.user, max_age_seconds=1)
        # Advance time by 2 seconds
        with mock.patch("time.time", return_value=time.time() + 2):
            self.assertFalse(verify_step_up_token(token, self.user, max_age_seconds=1))

    def test_step_up_middleware(self):
        token = generate_step_up_token(self.user, max_age_seconds=300)
        request = self.factory.get("/", HTTP_X_STEP_UP_TOKEN=token)
        request.user = self.user

        middleware = StepUpAuthMiddleware(lambda req: Response({"ok": True}))
        response = middleware(request)

        self.assertTrue(getattr(request, "is_step_up_authenticated", False))
        self.assertEqual(getattr(request, "step_up_token", None), token)

    def test_permission_class_prompt_when_stale(self):
        request = self.factory.post("/")
        # Simulate stale token (issued 10 minutes ago)
        force_authenticate(request, user=self.user, token={"iat": time.time() - 600})

        view = DummyProtectedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            "step_up_required" in str(response.data)
            or "Step-up authentication required" in str(response.data)
        )

    def test_permission_class_allows_when_recent(self):
        request = self.factory.post("/")
        # Recent authentication (1 minute ago)
        force_authenticate(request, user=self.user, token={"iat": time.time() - 60})

        view = DummyProtectedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "sensitive_action_completed")

    def test_permission_class_allows_with_step_up_token_header(self):
        token = generate_step_up_token(self.user, max_age_seconds=300)
        request = self.factory.post("/", HTTP_X_STEP_UP_TOKEN=token)
        force_authenticate(request, user=self.user, token={"iat": time.time() - 600})

        view = DummyProtectedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_decorator_prompt_when_stale(self):
        request = self.factory.post("/")
        force_authenticate(request, user=self.user, token={"iat": time.time() - 600})

        view = DummyDecoratedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("error"), "step_up_required")

    def test_decorator_allows_when_recent(self):
        request = self.factory.post("/")
        force_authenticate(request, user=self.user, token={"iat": time.time() - 30})

        view = DummyDecoratedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class StepUpEndpointsIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = "StrongPassword123!"
        self.user = User.objects.create_user(
            username="alice_mfa",
            email="alice_mfa@example.com",
            password=self.password,
        )
        self.client = APIClient()
        # Create an initial session
        self.session = UserSession.objects.create(
            user=self.user,
            ip_address="127.0.0.1",
            user_agent="Firefox",
        )

    def test_step_up_verify_endpoint_with_password(self):
        self.client.force_authenticate(user=self.user)
        # Invalid password
        resp = self.client.post("/api/auth/step-up/verify/", {"password": "WrongPassword!"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid password
        resp = self.client.post("/api/auth/step-up/verify/", {"password": self.password})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = resp.data.get("step_up_token")
        self.assertIsNotNone(token)
        self.assertTrue(verify_step_up_token(token, self.user))

    def test_email_change_requires_step_up_and_invalidates_sessions(self):
        self.client.force_authenticate(user=self.user)

        # 1. Update non-sensitive field (bio) - should succeed without step-up
        resp = self.client.put("/api/auth/me/", {"bio": "Hello world!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Update email without step-up token when auth is stale
        with mock.patch("apps.accounts.views.is_recently_authenticated", return_value=False):
            resp = self.client.put("/api/auth/me/", {"email": "new_alice@example.com"})
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIn("step_up_required", str(resp.data))

        # 3. Update email with recent authentication - should succeed and invalidate existing sessions
        other_session = UserSession.objects.create(
            user=self.user,
            ip_address="192.168.1.100",
            user_agent="Chrome on Laptop",
        )
        token = generate_step_up_token(self.user, max_age_seconds=300)
        resp = self.client.put(
            "/api/auth/me/",
            {"email": "new_alice@example.com"},
            HTTP_X_STEP_UP_TOKEN=token,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new_alice@example.com")
        # Ensure sessions were revoked upon sensitive email change
        self.assertFalse(UserSession.objects.filter(pk=other_session.pk).exists())

    def test_2fa_disable_requires_step_up_and_invalidates_sessions(self):
        # Enable TOTP device on user
        from apps.accounts.models import TOTPDevice
        TOTPDevice.objects.create(
            user=self.user,
            secret="JBSWY3DPEHPK3PXP",
            is_enabled=True,
        )
        other_session = UserSession.objects.create(
            user=self.user,
            ip_address="10.0.0.5",
            user_agent="Mobile Safari",
        )

        self.client.force_authenticate(user=self.user)

        # Disabling without step-up when auth is stale
        with mock.patch("apps.accounts.views.is_recently_authenticated", return_value=False):
            resp = self.client.post("/api/auth/2fa/disable/", {"password": self.password})
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIn("step_up_required", str(resp.data))

        # Disabling with valid step-up token
        token = generate_step_up_token(self.user, max_age_seconds=300)
        resp = self.client.post(
            "/api/auth/2fa/disable/",
            {"password": self.password},
            HTTP_X_STEP_UP_TOKEN=token,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        # Ensure sessions were revoked upon 2FA removal
        self.assertFalse(UserSession.objects.filter(pk=other_session.pk).exists())
