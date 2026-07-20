from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Organization, OrganizationAuditLog, OrganizationMembership


class OrganizationViewSetTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="password123")
        self.admin = User.objects.create_user(username="admin", password="password123")
        self.member = User.objects.create_user(username="member", password="password123")
        self.outsider = User.objects.create_user(
            username="outsider", password="password123"
        )

        self.org = Organization.objects.create(name="Test Org", description="Test Desc")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.ROLE_OWNER
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.ROLE_ADMIN
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.ROLE_MEMBER,
        )

        self.list_url = "/api/organizations/"
        self.detail_url = f"/api/organizations/{self.org.id}/"

    # ---------------------------------------------------------------- list

    def test_list_organizations_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_organizations_only_returns_orgs_user_belongs_to(self):
        other_org = Organization.objects.create(name="Other Org")
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        returned_ids = {org["id"] for org in results}
        self.assertIn(self.org.id, returned_ids)
        self.assertNotIn(other_org.id, returned_ids)

    def test_outsider_cannot_see_org_in_list(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.list_url)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 0)

    # -------------------------------------------------------------- create

    def test_create_organization_makes_creator_owner(self):
        self.client.force_authenticate(user=self.outsider)
        data = {"name": "New Org", "description": "New Desc"}
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        new_org = Organization.objects.get(name="New Org")
        membership = OrganizationMembership.objects.get(
            organization=new_org, user=self.outsider
        )
        self.assertEqual(membership.role, OrganizationMembership.ROLE_OWNER)
        self.assertTrue(
            OrganizationAuditLog.objects.filter(
                organization_id=new_org.id, action=OrganizationAuditLog.ACTION_CREATED
            ).exists()
        )

    # ------------------------------------------------------------- detail

    def test_outsider_cannot_retrieve_org_detail(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_retrieve_org_detail(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["my_role"], "member")

    # ------------------------------------------------------------- update

    def test_member_cannot_update_org(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.patch(self.detail_url, {"description": "hacked"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_org(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(self.detail_url, {"description": "updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.description, "updated")
        self.assertTrue(
            OrganizationAuditLog.objects.filter(
                organization_id=self.org.id, action=OrganizationAuditLog.ACTION_UPDATED
            ).exists()
        )

    # ------------------------------------------------------------- delete

    def test_member_cannot_delete_org(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Organization.objects.filter(id=self.org.id).exists())

    def test_owner_can_delete_org_and_memberships_cascade(self):
        org_id = self.org.id
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Organization.objects.filter(id=org_id).exists())
        # Cascade delete: memberships should be gone too
        self.assertFalse(
            OrganizationMembership.objects.filter(organization_id=org_id).exists()
        )
        # Audit log persists (not tied to the org via FK cascade)
        self.assertTrue(
            OrganizationAuditLog.objects.filter(
                organization_id=org_id, action=OrganizationAuditLog.ACTION_DELETED
            ).exists()
        )

    def test_user_delete_cascades_memberships(self):
        user_id = self.member.id
        self.member.delete()
        self.assertFalse(
            OrganizationMembership.objects.filter(user_id=user_id).exists()
        )


class OrganizationMembershipViewSetTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner2", password="password123")
        self.member = User.objects.create_user(
            username="member2", password="password123"
        )
        self.new_user = User.objects.create_user(
            username="newbie", password="password123"
        )
        self.org = Organization.objects.create(name="Membership Org")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.ROLE_OWNER
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.ROLE_MEMBER,
        )
        self.members_url = f"/api/organizations/{self.org.id}/members/"

    def test_member_cannot_add_members(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            self.members_url, {"user": self.new_user.id, "role": "member"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_add_member(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.members_url, {"user": self.new_user.id, "role": "member"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.org, user=self.new_user
            ).exists()
        )

    def test_cannot_remove_last_owner(self):
        self.client.force_authenticate(user=self.owner)
        membership = OrganizationMembership.objects.get(
            organization=self.org, user=self.owner
        )
        response = self.client.delete(f"{self.members_url}{membership.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            OrganizationMembership.objects.filter(id=membership.id).exists()
        )
