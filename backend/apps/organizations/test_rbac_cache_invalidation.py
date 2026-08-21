from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.permissions import (
    IsOrganizationAdminOrOwner,
    IsOrganizationMember,
    get_cached_organization_role,
)

User = get_user_model()


class OrganizationRBACCacheInvalidationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="test_member", password="password123"
        )
        self.org = Organization.objects.create(
            name="Cache Test Org", description="Testing RBAC cache invalidation"
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.ROLE_MEMBER,
        )

    def tearDown(self):
        cache.clear()

    def test_organization_role_is_cached(self):
        """Initial role check should query DB and cache the result."""
        cache_key = f"org:user_role:{self.user.id}:{self.org.id}"
        self.assertIsNone(cache.get(cache_key))

        role = get_cached_organization_role(self.user.id, self.org.id)
        self.assertEqual(role, OrganizationMembership.ROLE_MEMBER)
        self.assertEqual(cache.get(cache_key), OrganizationMembership.ROLE_MEMBER)

    def test_role_update_invalidates_cache_immediately(self):
        """Updating member role to admin should invalidate cache and return new role."""
        # Populate cache
        role = get_cached_organization_role(self.user.id, self.org.id)
        self.assertEqual(role, OrganizationMembership.ROLE_MEMBER)

        # Update role via model save
        self.membership.role = OrganizationMembership.ROLE_ADMIN
        self.membership.save()

        # Cached entry should be invalidated and return new role
        updated_role = get_cached_organization_role(self.user.id, self.org.id)
        self.assertEqual(updated_role, OrganizationMembership.ROLE_ADMIN)

    def test_membership_deletion_invalidates_cache(self):
        """Deleting membership should invalidate cache and return None."""
        # Populate cache
        role = get_cached_organization_role(self.user.id, self.org.id)
        self.assertEqual(role, OrganizationMembership.ROLE_MEMBER)

        # Delete membership
        self.membership.delete()

        # Cache should be invalidated and return None
        new_role = get_cached_organization_role(self.user.id, self.org.id)
        self.assertIsNone(new_role)

    def test_permissions_reflect_invalidated_cache(self):
        """Permission checks adapt dynamically as organization membership roles change."""
        perm = IsOrganizationAdminOrOwner()

        class MockRequest:
            user = self.user
            method = "DELETE"

        request = MockRequest()

        # Initially member (unsafe DELETE rejected)
        self.assertFalse(perm.has_object_permission(request, None, self.org))

        # Promote to admin -> should immediately be allowed due to cache invalidation
        self.membership.role = OrganizationMembership.ROLE_ADMIN
        self.membership.save()

        self.assertTrue(perm.has_object_permission(request, None, self.org))
