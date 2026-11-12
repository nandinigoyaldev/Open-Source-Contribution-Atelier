"""
Unit tests for tenant-aware cache key enforcement, collision detection,
and tenant invalidation APIs.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.cache.services.cache_manager import (
    CacheKeyCollisionError,
    CacheManager,
    TenantContextRequiredError,
    cached,
    invalidates,
)
from apps.organizations.signals import invalidate_user_organization_rbac_cache


class TenantAwareCacheKeyEnforcementTest(SimpleTestCase):
    """
    Validates tenant-aware cache key generation, strict tenant context enforcement,
    and cross-tenant isolation at the shared cache layer.
    """

    def setUp(self):
        super().setUp()
        self.manager = CacheManager()
        cache.clear()
        self.manager.reset_collision_registry()
        self.manager.enable_collision_detection(False)

    def tearDown(self):
        super().tearDown()
        cache.clear()
        self.manager.reset_collision_registry()
        self.manager.enable_collision_detection(False)

    def test_get_tenant_cache_key_format(self):
        """Tenant cache key should be namespaced with tenant ID."""
        key = self.manager.get_tenant_cache_key("org_100", "analytics")
        self.assertTrue(key.startswith("cache:tenant:org_100:analytics:"))

        # Integer tenant ID should be string-normalized
        key_str = self.manager.get_tenant_cache_key("100", "analytics")
        key_int = self.manager.get_tenant_cache_key(100, "analytics")
        self.assertEqual(key_str, key_int)

        # User-scoped tenant key includes user namespace
        key_user = self.manager.get_tenant_cache_key("org_100", "profile", user_id=42)
        self.assertTrue(key_user.startswith("cache:tenant:org_100:user:42:profile:"))

    def test_tenant_context_required_missing_tenant_id(self):
        """Missing or None tenant_id must raise TenantContextRequiredError."""
        with self.assertRaises(TenantContextRequiredError) as ctx:
            self.manager.get_tenant_cache_key(None, "user_profile", user_id=1)
        self.assertIn("tenant_id is required", str(ctx.exception))

    def test_tenant_context_required_empty_tenant_id(self):
        """Empty or whitespace-only tenant_id must raise TenantContextRequiredError."""
        for empty_val in ("", "   "):
            with self.assertRaises(TenantContextRequiredError) as ctx:
                self.manager.get_tenant_cache_key(empty_val, "user_profile")
            self.assertIn("tenant_id cannot be empty", str(ctx.exception))

    def test_cross_tenant_isolation(self):
        """Identical resources for different tenants must generate distinct keys and values."""
        key_org_a = self.manager.get_tenant_cache_key(
            "tenant_a", "metrics", date="2026-11-11"
        )
        key_org_b = self.manager.get_tenant_cache_key(
            "tenant_b", "metrics", date="2026-11-11"
        )

        self.assertNotEqual(key_org_a, key_org_b)

        # Store distinct tenant data
        self.manager.set(key_org_a, {"score": 95})
        self.manager.set(key_org_b, {"score": 40})

        # Ensure no cross-tenant leakage
        self.assertEqual(self.manager.get(key_org_a)["score"], 95)
        self.assertEqual(self.manager.get(key_org_b)["score"], 40)

    def test_get_global_cache_key(self):
        """Global cache key must be explicitly separated from tenant namespace."""
        key_global = self.manager.get_global_cache_key(
            "system_config", setting="maintenance"
        )
        self.assertTrue(key_global.startswith("cache:global:system_config:"))

    def test_get_cache_key_with_tenant_kwarg(self):
        """Passing tenant_id or organization_id in kwargs must delegate to get_tenant_cache_key."""
        key_direct = self.manager.get_tenant_cache_key(12, "project_list")
        key_kwarg = self.manager.get_cache_key("project_list", tenant_id=12)
        key_org_kwarg = self.manager.get_cache_key("project_list", organization_id=12)

        self.assertEqual(key_direct, key_kwarg)
        self.assertEqual(key_direct, key_org_kwarg)

    def test_get_cache_key_tenant_scoped_flag(self):
        """tenant_scoped=True requires a tenant context or raises error."""
        with self.assertRaises(TenantContextRequiredError):
            self.manager.get_cache_key("tenant_data", tenant_scoped=True)

        key = self.manager.get_cache_key(
            "tenant_data", tenant_id="org_5", tenant_scoped=True
        )
        self.assertTrue(key.startswith("cache:tenant:org_5:tenant_data:"))

    def test_collision_detection_in_dev_test(self):
        """Collision detection raises error if cross-tenant key conflict occurs."""
        self.manager.enable_collision_detection(True)

        key1 = self.manager.get_tenant_cache_key("org_1", "dashboard", view="summary")
        self.assertIn(key1, CacheManager._key_registry)

        # Manually verify that attempting to register an identical key with another tenant raises
        with self.assertRaises(CacheKeyCollisionError):
            self.manager._record_and_check_collision(
                key=key1,
                tenant_id="org_2",
                prefix="dashboard",
                args=(),
                kwargs={"view": "summary"},
            )

    def test_invalidate_tenant(self):
        """invalidate_tenant clears all entries for the target tenant only."""
        key_t1_a = self.manager.get_tenant_cache_key("org_alpha", "report", id=1)
        key_t1_b = self.manager.get_tenant_cache_key("org_alpha", "settings")
        key_t2 = self.manager.get_tenant_cache_key("org_beta", "report", id=1)

        self.manager.set(key_t1_a, "alpha_report")
        self.manager.set(key_t1_b, "alpha_settings")
        self.manager.set(key_t2, "beta_report")

        # Invalidate org_alpha
        self.manager.invalidate_tenant("org_alpha")

        self.assertIsNone(self.manager.get(key_t1_a))
        self.assertIsNone(self.manager.get(key_t1_b))
        # org_beta must remain intact
        self.assertEqual(self.manager.get(key_t2), "beta_report")

    def test_invalidate_tenant_with_prefix(self):
        """invalidate_tenant with prefix removes only matching entries for that tenant."""
        key_report = self.manager.get_tenant_cache_key("org_gamma", "report", id=1)
        key_settings = self.manager.get_tenant_cache_key("org_gamma", "settings")

        self.manager.set(key_report, "report_data")
        self.manager.set(key_settings, "settings_data")

        self.manager.invalidate_tenant("org_gamma", prefix="report")

        self.assertIsNone(self.manager.get(key_report))
        self.assertEqual(self.manager.get(key_settings), "settings_data")

    def test_invalidate_tenant_user(self):
        """invalidate_tenant_user clears user-specific entries within a tenant."""
        key_user = self.manager.get_tenant_cache_key(
            "org_delta", "user_profile", user_id=99
        )
        key_other = self.manager.get_tenant_cache_key("org_delta", "org_overview")

        self.manager.set(key_user, "user_profile_data")
        self.manager.set(key_other, "overview_data")

        self.manager.invalidate_tenant_user("org_delta", 99)

        self.assertIsNone(self.manager.get(key_user))
        self.assertEqual(self.manager.get(key_other), "overview_data")

    def test_cached_decorator_tenant_scoped(self):
        """@cached(tenant_scoped=True) maintains tenant isolation and caches per tenant."""
        call_count = 0

        @cached(prefix="org_computation", tenant_scoped=True)
        def compute_org_value(tenant_id, factor):
            nonlocal call_count
            call_count += 1
            return f"{tenant_id}-{factor * 10}"

        # First call computes
        val1 = compute_org_value("tenant_x", 2)
        self.assertEqual(val1, "tenant_x-20")
        self.assertEqual(call_count, 1)

        # Second call hits cache
        val1_cached = compute_org_value("tenant_x", 2)
        self.assertEqual(val1_cached, "tenant_x-20")
        self.assertEqual(call_count, 1)

        # Different tenant computes separately
        val2 = compute_org_value("tenant_y", 2)
        self.assertEqual(val2, "tenant_y-20")
        self.assertEqual(call_count, 2)

    def test_cached_decorator_tenant_scoped_missing_tenant_error(self):
        """@cached(tenant_scoped=True) raises error if tenant_id cannot be resolved."""

        @cached(prefix="scoped_no_tenant", tenant_scoped=True)
        def func_without_tenant(x, y):
            return x + y

        with self.assertRaises(TenantContextRequiredError):
            func_without_tenant(1, 2)

    def test_invalidates_decorator_tenant_scoped(self):
        """@invalidates(tenant_scoped=True) invalidates cache upon completion."""
        key = self.manager.get_tenant_cache_key("org_omega", "status")
        self.manager.set(key, "old_status")

        @invalidates("status", tenant_scoped=True)
        def update_org_status(tenant_id, new_val):
            return new_val

        update_org_status("org_omega", "new_status")
        self.assertIsNone(self.manager.get(key))

    @patch.object(CacheManager, "invalidate_tenant_user")
    def test_organization_membership_signal_triggers_tenant_invalidation(
        self, mock_inv
    ):
        """Modifying membership invokes tenant user cache invalidation."""
        invalidate_user_organization_rbac_cache(user_id=55, organization_id=101)
        mock_inv.assert_called_once_with(101, 55)
