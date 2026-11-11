import waffle
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase
from waffle.models import Flag, Switch

from .context_processors import feature_flags
from .middleware import FeatureFlags, FeatureFlagsMiddleware


class FeatureFlagContextProcessorTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_feature_flags_in_context_with_switches(self):
        Switch.objects.create(name="beta_search", active=True)
        Switch.objects.create(name="dark_mode", active=False)

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["switches"]["beta_search"]["enabled"])
        self.assertFalse(context["feature_flags"]["switches"]["dark_mode"]["enabled"])

    def test_feature_flags_in_context_with_flags(self):
        user = User.objects.create_user("testuser")
        flag = Flag.objects.create(name="new_ui", everyone=True)
        flag.users.add(user)

        request = RequestFactory().get("/")
        request.user = user
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["flags"]["new_ui"]["enabled"])


class FeatureFlagsMiddlewareTests(TestCase):
    """`request.feature_flags` must be usable on guest requests (issue #2653)."""

    def setUp(self):
        from django.core.cache import cache

        # waffle caches flags outside the test transaction; clear between tests.
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = FeatureFlagsMiddleware(lambda request: "response")

    def _guest_request(self, path="/"):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return request

    def test_guest_request_gets_feature_flags_accessor(self):
        request = self._guest_request()

        self.middleware(request)

        self.assertIsInstance(request.feature_flags, FeatureFlags)

    def test_guest_unknown_flag_is_false_not_attribute_error(self):
        request = self._guest_request()

        self.middleware(request)

        # The scenario from the issue: a guest hits a view that reads a flag.
        self.assertIs(request.feature_flags.is_enabled("new_landing"), False)

    def test_guest_request_evaluates_everyone_flag(self):
        Flag.objects.create(name="new_landing", everyone=True)
        request = self._guest_request()

        self.middleware(request)

        self.assertIs(request.feature_flags.is_enabled("new_landing"), True)

    def test_guest_request_respects_everyone_false(self):
        Flag.objects.create(name="new_landing", everyone=False)
        request = self._guest_request()

        self.middleware(request)

        self.assertIs(request.feature_flags.is_enabled("new_landing"), False)

    def test_authenticated_request_also_gets_accessor(self):
        Flag.objects.create(name="new_landing", everyone=True)
        request = self.factory.get("/")
        request.user = User.objects.create_user("member")

        self.middleware(request)

        self.assertIsInstance(request.feature_flags, FeatureFlags)
        self.assertIs(request.feature_flags.is_enabled("new_landing"), True)

    def test_middleware_returns_downstream_response(self):
        request = self._guest_request()

        self.assertEqual(self.middleware(request), "response")


class DatabaseBackedFeatureFlagTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from apps.feature_flags.models import FeatureFlag, FeatureFlagAuditLog

        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_user",
            password="Password123!",
            email="admin@example.com",
        )
        self.normal_user = User.objects.create_user(
            username="normal_user",
            password="Password123!",
            email="user@example.com",
        )
        FeatureFlag.objects.all().delete()
        FeatureFlagAuditLog.objects.all().delete()

    def test_default_behavior(self):
        from apps.feature_flags.models import FeatureFlag
        from apps.feature_flags.services import evaluate_feature_flag

        flag = FeatureFlag.objects.create(
            name="new_feature",
            is_active=False,
            default_value=False,
        )
        enabled, reason = evaluate_feature_flag(flag, user=self.normal_user)
        self.assertFalse(enabled)
        self.assertEqual(reason, "flag_inactive")

        # Inactive flag with default_value=True returns True
        flag.default_value = True
        flag.save()
        enabled, _ = evaluate_feature_flag(flag, user=self.normal_user)
        self.assertTrue(enabled)

    def test_deterministic_percentage_targeting(self):
        from apps.feature_flags.models import FeatureFlag
        from apps.feature_flags.services import (
            compute_deterministic_bucket,
            evaluate_feature_flag,
        )

        flag = FeatureFlag.objects.create(
            name="canary_rollout",
            flag_type="percentage",
            is_active=True,
            rollout_percentage=50,
        )

        # Deterministic: evaluating 100 times for the same user yields the same result
        first_res, _ = evaluate_feature_flag(flag, user="stable_user_1")
        for _ in range(20):
            res, _ = evaluate_feature_flag(flag, user="stable_user_1")
            self.assertEqual(res, first_res)

        bucket = compute_deterministic_bucket("stable_user_1", salt=flag.name)
        self.assertEqual(first_res, bucket < 50)

    def test_organization_targeting_isolation(self):
        from apps.feature_flags.models import FeatureFlag
        from apps.feature_flags.services import evaluate_feature_flag

        flag = FeatureFlag.objects.create(
            name="enterprise_reporting",
            flag_type="organization",
            is_active=True,
            target_organizations=["org_alpha", "org_beta"],
        )

        # Targeted org is enabled
        enabled, reason = evaluate_feature_flag(flag, organization="org_alpha")
        self.assertTrue(enabled)
        self.assertIn("organization_targeted", reason)

        # Untargeted org is strictly disabled (isolation)
        enabled_other, reason_other = evaluate_feature_flag(
            flag, organization="org_gamma"
        )
        self.assertFalse(enabled_other)
        self.assertIn("organization_not_in_targets", reason_other)

    def test_audit_logging_and_rollback(self):
        from apps.feature_flags.models import FeatureFlag
        from apps.feature_flags.services import (
            record_flag_change,
            rollback_feature_flag,
        )

        flag = FeatureFlag.objects.create(
            name="checkout_flow",
            is_active=False,
            rollout_percentage=0,
        )
        record_flag_change(
            flag=flag,
            actor=self.admin,
            action="created",
            old_values={},
            new_values={"is_active": False, "rollout_percentage": 0},
            reason="Initial creation",
        )

        # Admin changes flag to 100% active
        old_val = {"is_active": False, "rollout_percentage": 0}
        flag.is_active = True
        flag.rollout_percentage = 100
        flag.save()
        record_flag_change(
            flag=flag,
            actor=self.admin,
            action="updated",
            old_values=old_val,
            new_values={"is_active": True, "rollout_percentage": 100},
            reason="Full rollout deployment",
        )

        self.assertEqual(flag.audit_logs.count(), 2)

        # One-action rollback restores previous configuration
        rollback_log = rollback_feature_flag(
            flag=flag, actor=self.admin, reason="Emergency incident mitigation"
        )
        flag.refresh_from_db()
        self.assertFalse(flag.is_active)
        self.assertEqual(flag.rollout_percentage, 0)
        self.assertEqual(rollback_log.action, "rolled_back")
        self.assertEqual(flag.audit_logs.count(), 3)

    def test_unauthorized_changes_rejected(self):
        from apps.feature_flags.models import FeatureFlag

        flag = FeatureFlag.objects.create(name="secret_feature", is_active=False)

        # Unauthenticated -> 401
        res = self.client.patch(
            f"/api/feature-flags/{flag.id}/", {"is_active": True}
        )
        self.assertEqual(res.status_code, 401)

        # Authenticated non-admin user -> 403 Forbidden
        self.client.force_authenticate(user=self.normal_user)
        res2 = self.client.patch(
            f"/api/feature-flags/{flag.id}/", {"is_active": True}
        )
        self.assertEqual(res2.status_code, 403)
        flag.refresh_from_db()
        self.assertFalse(flag.is_active)

        # Admin user -> 200 OK
        self.client.force_authenticate(user=self.admin)
        res3 = self.client.patch(
            f"/api/feature-flags/{flag.id}/",
            {"is_active": True, "change_reason": "Approved launch"},
        )
        self.assertEqual(res3.status_code, 200)
        flag.refresh_from_db()
        self.assertTrue(flag.is_active)

    def test_dry_run_endpoint(self):
        from apps.feature_flags.models import FeatureFlag

        flag = FeatureFlag.objects.create(
            name="ai_assistant",
            flag_type="organization",
            is_active=True,
            target_organizations=["beta_partners"],
        )

        self.client.force_authenticate(user=self.admin)
        payload = {"flag_name": "ai_assistant", "organization": "beta_partners"}
        res = self.client.post("/api/feature-flags/dry-run/", payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_enabled"])
        self.assertIn("organization_targeted", res.data["reason"])
