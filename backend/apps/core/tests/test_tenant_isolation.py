"""
Integration tests for cross-tenant data isolation (issue #1940).

These tests verify that an authenticated user in Organization A cannot
list or retrieve resources owned by Organization B, and that the
tenant-scoping primitives behave correctly.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.core.tenant import (
    set_current_tenant,
    clear_current_tenant,
    get_current_tenant_id,
)
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org_a(db):
    return Organization.objects.create(name="Org A")


@pytest.fixture
def org_b(db):
    return Organization.objects.create(name="Org B")


@pytest.fixture
def user_a(db, org_a):
    user = User.objects.create_user(
        username="alice", email="alice@example.com", password="pw123456"
    )
    # Profile is auto-created by signal in apps.accounts; set the org.
    profile = getattr(user, "user_profile", None)
    if profile is None:
        from apps.accounts.models import UserProfile

        profile = UserProfile.objects.create(user=user)
    profile.organization = org_a
    profile.save()
    OrganizationMembership.objects.create(
        organization=org_a, user=user, role=OrganizationMembership.ROLE_MEMBER
    )
    return user


@pytest.fixture
def user_b(db, org_b):
    user = User.objects.create_user(
        username="bob", email="bob@example.com", password="pw123456"
    )
    profile = getattr(user, "user_profile", None)
    if profile is None:
        from apps.accounts.models import UserProfile

        profile = UserProfile.objects.create(user=user)
    profile.organization = org_b
    profile.save()
    OrganizationMembership.objects.create(
        organization=org_b, user=user, role=OrganizationMembership.ROLE_MEMBER
    )
    return user


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def authed_client_a(api_client, user_a):
    api_client.force_authenticate(user=user_a)
    return api_client


@pytest.fixture
def authed_client_b(api_client, user_b):
    api_client.force_authenticate(user=user_b)
    return api_client


# ---------------------------------------------------------------------------
# Thread-local tenant context
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTenantContext:
    def test_set_and_get_tenant(self):
        set_current_tenant(organization_id=42, user_id=7)
        assert get_current_tenant_id() == 42
        clear_current_tenant()
        assert get_current_tenant_id() is None

    def test_clear_is_idempotent(self):
        clear_current_tenant()
        clear_current_tenant()
        assert get_current_tenant_id() is None


# ---------------------------------------------------------------------------
# Middleware-style resolution (via force_authenticate + request)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTenantMiddlewareResolution:
    def test_middleware_sets_org_from_profile(self, api_client, user_a, org_a):
        from apps.core.middleware.tenant import TenantContextMiddleware

        class _DummyResponse:
            pass

        captured = {}

        def get_response(request):
            captured["org"] = get_current_tenant_id()
            return _DummyResponse()

        mw = TenantContextMiddleware(get_response)
        # Build a minimal request with .user attached.
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/api/anything/")
        request.user = user_a
        mw(request)
        assert captured["org"] == org_a.id
        # Context is cleared after the request.
        assert get_current_tenant_id() is None


# ---------------------------------------------------------------------------
# Cross-tenant API access (Organizations app)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCrossTenantOrganizationAccess:
    """
    Org A user must NOT see Org B in list or detail.
    """

    def test_list_excludes_other_tenant(self, authed_client_a, org_b):
        response = authed_client_a.get("/api/organizations/")
        ids = [o["id"] for o in response.data.get("results", response.data)]
        assert response.status_code == 200
        assert org_b.id not in ids

    def test_detail_other_tenant_rejected(self, authed_client_a, org_b):
        response = authed_client_a.get(f"/api/organizations/{org_b.id}/")
        # 404 is the secure default: existence of the resource is not leaked.
        assert response.status_code in (403, 404)

    def test_member_cannot_access_other_org_memberships(
        self, authed_client_a, org_b, user_b
    ):
        response = authed_client_a.get(f"/api/organizations/{org_b.id}/members/")
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# IsTenantMember permission
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIsTenantMemberPermission:
    def test_object_in_same_tenant_allowed(self, user_a, org_a):
        from apps.core.permissions import IsTenantMember

        class _Obj:
            organization_id = org_a.id

        perm = IsTenantMember()
        set_current_tenant(org_a.id, user_a.id)
        try:

            class _Req:
                user = user_a

            assert perm.has_object_permission(_Req(), None, _Obj()) is True
        finally:
            clear_current_tenant()

    def test_object_in_other_tenant_denied(self, user_a, org_a, org_b):
        from apps.core.permissions import IsTenantMember

        class _Obj:
            organization_id = org_b.id

        perm = IsTenantMember()
        set_current_tenant(org_a.id, user_a.id)
        try:

            class _Req:
                user = user_a

            assert perm.has_object_permission(_Req(), None, _Obj()) is False
        finally:
            clear_current_tenant()


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditCommand:
    def test_command_runs_and_reports(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        # Should not raise; --strict would exit nonzero if any gap exists,
        # so we run WITHOUT --strict here and just assert it produces output.
        call_command("audit_tenant_isolation", stdout=out)
        text = out.getvalue()
        assert "Audited" in text
