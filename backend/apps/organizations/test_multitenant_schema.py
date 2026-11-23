from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from apps.core.tenant import clear_current_tenant, get_current_schema
from apps.organizations.middleware import TenantSchemaMiddleware
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer
from apps.organizations.tenancy import (
    activate_tenant_schema,
    create_tenant_schema,
    deactivate_tenant_schema,
    get_tenant_schema_name,
    is_valid_schema_name,
)


class MultiTenantSchemaRoutingTests(TestCase):
    def setUp(self):
        super().setUp()
        clear_current_tenant()
        self.factory = RequestFactory()

    def tearDown(self):
        clear_current_tenant()
        super().tearDown()

    def test_get_tenant_schema_name_formatting(self):
        self.assertEqual(get_tenant_schema_name("acme"), "tenant_acme")
        self.assertEqual(get_tenant_schema_name("acme-corp"), "tenant_acme_corp")
        self.assertEqual(
            get_tenant_schema_name("My Enterprise!"), "tenant_my_enterprise"
        )
        self.assertEqual(get_tenant_schema_name(""), "tenant_org")

        # Must not exceed PostgreSQL's 63-byte identifier limit
        very_long = "a" * 100
        schema = get_tenant_schema_name(very_long)
        self.assertLessEqual(len(schema), 63)
        self.assertTrue(schema.startswith("tenant_"))

    def test_schema_name_validation(self):
        self.assertTrue(is_valid_schema_name("tenant_acme"))
        self.assertTrue(is_valid_schema_name("tenant_12345"))
        self.assertTrue(is_valid_schema_name("public"))

        # Rejects SQL injection attempts and invalid identifiers
        self.assertFalse(is_valid_schema_name("tenant; DROP TABLE users;"))
        self.assertFalse(is_valid_schema_name('tenant"acme'))
        self.assertFalse(is_valid_schema_name("123_invalid_start"))
        self.assertFalse(is_valid_schema_name(""))

    def test_activate_tenant_schema_generates_search_path_sql(self):
        sql = activate_tenant_schema("tenant_acme_corp")
        self.assertEqual(sql, 'SET search_path TO "tenant_acme_corp", public')
        self.assertEqual(get_current_schema(), "tenant_acme_corp")

        reset_sql = deactivate_tenant_schema()
        self.assertEqual(reset_sql, "SET search_path TO public")
        self.assertEqual(get_current_schema(), "public")

    def test_activate_tenant_schema_rejects_malicious_names(self):
        with self.assertRaises(ValueError):
            activate_tenant_schema("tenant; DROP TABLE auth_user;")

    @patch("django.db.connection.cursor")
    def test_activate_tenant_schema_executes_on_postgresql(self, mock_cursor_func):
        mock_cursor = MagicMock()
        mock_cursor_func.return_value.__enter__.return_value = mock_cursor

        with patch("django.db.connection.vendor", "postgresql"):
            activate_tenant_schema("tenant_enterprise_beta")

        mock_cursor.execute.assert_called_with(
            'SET search_path TO "tenant_enterprise_beta", public'
        )

    def test_enterprise_organization_creation_auto_populates_schema(self):
        org = Organization.objects.create(
            name="Mega Corp Enterprise",
            is_enterprise=True,
        )

        self.assertEqual(org.slug, "mega-corp-enterprise")
        self.assertEqual(org.schema_name, "tenant_mega_corp_enterprise")
        self.assertTrue(org.is_enterprise)

    def test_community_organization_has_no_enterprise_schema_by_default(self):
        org = Organization.objects.create(
            name="Community Open Source Hub",
            is_enterprise=False,
        )

        self.assertEqual(org.slug, "community-open-source-hub")
        self.assertFalse(org.is_enterprise)
        self.assertIsNone(org.schema_name)

    @patch("apps.organizations.tenancy.migrate_tenant_schema")
    @patch("apps.organizations.tenancy.create_tenant_schema")
    def test_automated_schema_creation_and_migration_runner_on_save(
        self, mock_create, mock_migrate
    ):
        org = Organization.objects.create(
            name="Sponsor Tech Inc",
            is_enterprise=True,
        )

        mock_create.assert_called_with(org.schema_name)
        mock_migrate.assert_called_with(org.schema_name)

    def test_middleware_fast_path_for_default_community_users(self):
        request = self.factory.get("/api/dashboard/")
        middleware = TenantSchemaMiddleware(lambda req: req)

        with patch.object(middleware, "_resolve_organization") as mock_resolve:
            processed = middleware(request)
            # Fast path: community users never trigger organization lookup
            mock_resolve.assert_not_called()

        self.assertIsNone(processed.tenant)
        self.assertEqual(processed.tenant_schema, "public")
        self.assertEqual(get_current_schema(), "public")

    def test_middleware_enterprise_tenant_routing_via_header(self):
        org = Organization.objects.create(
            name="Acme Enterprise",
            is_enterprise=True,
        )

        request = self.factory.get(
            "/api/dashboard/",
            HTTP_X_ORGANIZATION_TENANT=org.slug,
        )

        def view(req):
            self.assertEqual(req.tenant, org)
            self.assertEqual(req.tenant_schema, org.schema_name)
            self.assertEqual(get_current_schema(), org.schema_name)
            return "OK"

        middleware = TenantSchemaMiddleware(view)
        response = middleware(request)

        self.assertEqual(response, "OK")
        # Ensure schema is reset to public after request completes
        self.assertEqual(get_current_schema(), "public")

    def test_middleware_enterprise_tenant_routing_via_subdomain(self):
        org = Organization.objects.create(
            name="FinTech Solutions",
            is_enterprise=True,
        )

        request = self.factory.get(
            "/api/challenges/",
            HTTP_HOST=f"{org.slug}.atelier.dev",
        )

        def view(req):
            self.assertEqual(req.tenant, org)
            self.assertEqual(req.tenant_schema, org.schema_name)
            self.assertEqual(get_current_schema(), org.schema_name)
            return "OK"

        middleware = TenantSchemaMiddleware(view)
        response = middleware(request)

        self.assertEqual(response, "OK")
        self.assertEqual(get_current_schema(), "public")

    def test_middleware_non_enterprise_organization_stays_on_public_schema(self):
        org = Organization.objects.create(
            name="Standard Community Team",
            is_enterprise=False,
        )

        request = self.factory.get(
            "/api/dashboard/",
            HTTP_X_ORGANIZATION_TENANT=org.slug,
        )

        def view(req):
            self.assertEqual(req.tenant, org)
            self.assertEqual(req.tenant_schema, "public")
            self.assertEqual(get_current_schema(), "public")
            return "OK"

        middleware = TenantSchemaMiddleware(view)
        response = middleware(request)

        self.assertEqual(response, "OK")
        self.assertEqual(get_current_schema(), "public")

    def test_organization_serializer_includes_enterprise_fields(self):
        org = Organization.objects.create(
            name="Global Enterprise Org",
            is_enterprise=True,
        )
        serializer = OrganizationSerializer(org)
        data = serializer.data

        self.assertIn("slug", data)
        self.assertIn("is_enterprise", data)
        self.assertIn("schema_name", data)
        self.assertEqual(data["slug"], "global-enterprise-org")
        self.assertTrue(data["is_enterprise"])
        self.assertEqual(data["schema_name"], "tenant_global_enterprise_org")
