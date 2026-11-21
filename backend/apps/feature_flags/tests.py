from typing import Any

import waffle
from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve
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
        res = self.client.patch(f"/api/feature-flags/{flag.id}/", {"is_active": True})
        self.assertEqual(res.status_code, 401)

        # Authenticated non-admin user -> 403 Forbidden
        self.client.force_authenticate(user=self.normal_user)
        res2 = self.client.patch(f"/api/feature-flags/{flag.id}/", {"is_active": True})
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


class FeatureFlagMigrationAndRoutingTests(TestCase):
    """The DB-backed flags need a migration and a route outside ``DEBUG`` (#3325)."""

    @override_settings(MIGRATION_MODULES={})
    def test_feature_flag_models_have_migrations(self):
        # --no-migrations swaps MIGRATION_MODULES out; read the real files again.
        try:
            call_command(
                "makemigrations",
                "feature_flags",
                check=True,
                dry_run=True,
                verbosity=0,
            )
        except SystemExit:
            self.fail("apps.feature_flags has model changes without a migration")

    def test_api_is_routed_when_debug_is_off(self):
        from django.conf import settings

        self.assertFalse(settings.DEBUG)
        self.assertEqual(
            resolve("/api/feature-flags/").func.cls.__name__, "FeatureFlagViewSet"
        )
        self.assertEqual(
            resolve("/api/v1/feature-flags/dry-run/").func.cls.__name__,
            "FeatureFlagViewSet",
        )


class FeatureFlagSafeRolloutTests(TestCase):
    """Environment scoping, kill switch and the outage default (#3325)."""

    def setUp(self):
        from django.core.cache import cache
        from rest_framework.test import APIClient

        cache.clear()
        self.api = APIClient()
        self.admin = User.objects.create_superuser(
            username="flag_admin", password="Password123!", email="a@example.com"
        )
        self.member = User.objects.create_user(
            username="member", password="Password123!", email="m@example.com"
        )
        self.factory = RequestFactory()

    def _flag(self, **kwargs):
        from apps.feature_flags.models import FeatureFlag

        defaults = {"name": "new_editor", "is_active": True}
        defaults.update(kwargs)
        return FeatureFlag.objects.create(**defaults)

    def _call(self, method: str, url: str, data=None, user=None) -> Any:
        self.api.force_authenticate(user=user)
        return getattr(self.api, method)(url, data, format="json")

    def _flags_for(self, user) -> Any:
        request: Any = self.factory.get("/")
        request.user = user
        FeatureFlagsMiddleware(lambda r: None)(request)
        return request.feature_flags

    # -- environment scoping -------------------------------------------------

    def test_flag_only_turns_on_in_its_environments(self):
        from apps.feature_flags.services import evaluate_feature_flag

        flag = self._flag(environments=["staging"], default_value=False)

        enabled, reason = evaluate_feature_flag(flag, environment="production")
        self.assertFalse(enabled)
        self.assertEqual(reason, "environment_out_of_scope (production)")

        enabled, reason = evaluate_feature_flag(flag, environment="Staging")
        self.assertTrue(enabled)
        self.assertEqual(reason, "flag_active_global")

    @override_settings(FEATURE_FLAG_ENVIRONMENT="staging")
    def test_environment_defaults_to_setting(self):
        from apps.feature_flags.services import evaluate_feature_flag

        self.assertTrue(evaluate_feature_flag(self._flag(environments=["staging"]))[0])
        prod_only = self._flag(name="prod_only", environments=["production"])
        self.assertFalse(evaluate_feature_flag(prod_only)[0])

    def test_update_normalizes_environments_and_audits_them(self):
        flag = self._flag()

        res = self._call(
            "patch",
            f"/api/feature-flags/{flag.id}/",
            {"environments": [" Staging ", "staging", "PROD"]},
            user=self.admin,
        )

        self.assertEqual(res.status_code, 200)
        flag.refresh_from_db()
        self.assertEqual(flag.environments, ["staging", "prod"])
        log = flag.audit_logs.get(action="updated")
        self.assertEqual(log.old_values["environments"], [])
        self.assertEqual(log.new_values["environments"], ["staging", "prod"])
        self.assertEqual(log.scope, "environment")

    # -- kill switch ---------------------------------------------------------

    def test_kill_switch_beats_targeting_and_default_value(self):
        from apps.feature_flags.services import evaluate_feature_flag

        flag = self._flag(default_value=True, target_users=["member"], kill_switch=True)

        self.assertEqual(
            evaluate_feature_flag(flag, user=self.member),
            (False, "kill_switch_engaged"),
        )

    def test_kill_switch_endpoint_records_before_and_after(self):
        flag = self._flag(rollout_percentage=40, flag_type="percentage")
        url = f"/api/feature-flags/{flag.id}/kill-switch/"

        res = self._call(
            "post", url, {"engaged": True, "reason": "incident 42"}, user=self.admin
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "updated")
        self.assertTrue(res.data["flag"]["kill_switch"])
        self.assertNotIn("target_users", res.data["flag"])
        log = flag.audit_logs.get()
        self.assertEqual(log.action, "kill_switch_engaged")
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.reason, "incident 42")
        self.assertFalse(log.old_values["kill_switch"])
        self.assertTrue(log.new_values["kill_switch"])
        self.assertEqual(log.new_values["rollout_percentage"], 40)

        # Pressing it again in the same incident is a no-op, not a second entry.
        again = self._call("post", url, {"engaged": True}, user=self.admin)
        self.assertEqual(again.data["status"], "unchanged")
        self.assertEqual(flag.audit_logs.count(), 1)

        released = self._call("post", url, {"engaged": False}, user=self.admin)
        self.assertEqual(released.data["status"], "updated")
        flag.refresh_from_db()
        self.assertFalse(flag.kill_switch)
        self.assertEqual(flag.audit_logs.first().action, "kill_switch_released")

    def test_kill_switch_cannot_be_flipped_by_patch_or_non_admins(self):
        flag = self._flag()
        url = f"/api/feature-flags/{flag.id}/kill-switch/"

        self.assertEqual(self._call("post", url, {"engaged": True}).status_code, 401)
        res = self._call("post", url, {"engaged": True}, user=self.member)
        self.assertEqual(res.status_code, 403)

        self._call(
            "patch",
            f"/api/feature-flags/{flag.id}/",
            {"kill_switch": True},
            user=self.admin,
        )
        flag.refresh_from_db()
        self.assertFalse(flag.kill_switch)

    # -- list endpoint used by the admin page ---------------------------------

    def test_list_is_admin_only_and_does_not_ship_targeting_ids(self):
        self._flag(
            target_users=["secret_user_1", "secret_user_2"],
            target_organizations=["acme_corp"],
            environments=["staging"],
        )

        res = self._call("get", "/api/feature-flags/", user=self.member)
        self.assertEqual(res.status_code, 403)

        res = self._call("get", "/api/feature-flags/", user=self.admin)

        self.assertEqual(res.status_code, 200)
        row = res.data[0]
        self.assertEqual(row["target_users_count"], 2)
        self.assertEqual(row["target_organizations_count"], 1)
        self.assertEqual(row["environments"], ["staging"])
        self.assertNotIn("target_users", row)
        self.assertNotIn(b"secret_user_1", res.content)
        self.assertNotIn(b"acme_corp", res.content)

    # -- safe default when the flag table cannot be read -----------------------

    def _db_down(self):
        from unittest import mock

        from django.db import OperationalError

        from apps.feature_flags.models import FeatureFlag

        return mock.patch.object(
            FeatureFlag.objects, "filter", side_effect=OperationalError("db down")
        )

    def test_outage_serves_last_known_state(self):
        self._flag(name="checkout_v2")
        self.assertTrue(self._flags_for(self.member).is_enabled("checkout_v2"))

        with self._db_down():
            self.assertTrue(self._flags_for(self.member).is_enabled("checkout_v2"))

    def test_outage_keeps_percentage_buckets_stable(self):
        from apps.feature_flags.services import compute_deterministic_bucket

        # Put "member" just inside the rollout so the bucket really decides it.
        bucket = compute_deterministic_bucket("member", salt="half")
        self._flag(name="half", flag_type="percentage", rollout_percentage=bucket + 1)
        self.assertTrue(self._flags_for(self.member).is_enabled("half"))
        other = User.objects.create_user(username="other")
        expected_other = compute_deterministic_bucket("other", salt="half") <= bucket
        self.assertEqual(self._flags_for(other).is_enabled("half"), expected_other)

        with self._db_down():
            self.assertTrue(self._flags_for(self.member).is_enabled("half"))
            self.assertEqual(self._flags_for(other).is_enabled("half"), expected_other)

    def test_outage_after_kill_switch_stays_off(self):
        from apps.feature_flags.services import set_kill_switch

        flag = self._flag(name="risky")
        self.assertTrue(self._flags_for(self.member).is_enabled("risky"))
        set_kill_switch(flag, engaged=True, actor=self.admin, reason="incident")

        with self._db_down():
            self.assertFalse(self._flags_for(self.member).is_enabled("risky"))

    def test_outage_without_last_known_state_is_off(self):
        Flag.objects.create(name="never_seen", everyone=True)

        with self._db_down():
            self.assertFalse(self._flags_for(self.member).is_enabled("never_seen"))

    def test_waffle_outage_returns_safe_default(self):
        from unittest import mock

        from django.db import OperationalError

        with mock.patch.object(
            waffle, "flag_is_active", side_effect=OperationalError("db down")
        ):
            self.assertFalse(self._flags_for(self.member).is_enabled("legacy"))
