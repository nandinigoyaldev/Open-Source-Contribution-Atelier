from apps.accounts.permissions import (
    IsAdminOrModeratorRole,
    IsAdminRole,
    IsModeratorRole,
)
from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView


class TestView(APIView):
    pass


class PermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = TestView.as_view()

        # Create groups
        self.admin_group = Group.objects.create(name="Admin")
        self.moderator_group = Group.objects.create(name="Moderator")

        # Create users
        self.regular_user = User.objects.create_user(
            username="regular", password="password"
        )

        self.admin_user = User.objects.create_user(
            username="admin", password="password"
        )
        self.admin_user.groups.add(self.admin_group)

        self.moderator_user = User.objects.create_user(
            username="moderator", password="password"
        )
        self.moderator_user.groups.add(self.moderator_group)

        self.staff_user = User.objects.create_user(
            username="staff", password="password", is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username="super", email="super@example.com", password="password"
        )

    def test_is_admin_role(self):
        permission = IsAdminRole()

        # Unauthenticated
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.assertFalse(permission.has_permission(request, self.view))

        # Regular user
        request = self.factory.get("/")
        request.user = self.regular_user
        self.assertFalse(permission.has_permission(request, self.view))

        # Moderator user
        request = self.factory.get("/")
        request.user = self.moderator_user
        self.assertFalse(permission.has_permission(request, self.view))

        # Admin group user
        request = self.factory.get("/")
        request.user = self.admin_user
        self.assertTrue(permission.has_permission(request, self.view))

        # Staff user
        request = self.factory.get("/")
        request.user = self.staff_user
        self.assertTrue(permission.has_permission(request, self.view))

        # Superuser
        request = self.factory.get("/")
        request.user = self.superuser
        self.assertTrue(permission.has_permission(request, self.view))

    def test_is_moderator_role(self):
        permission = IsModeratorRole()

        # Unauthenticated
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.assertFalse(permission.has_permission(request, self.view))

        # Regular user
        request = self.factory.get("/")
        request.user = self.regular_user
        self.assertFalse(permission.has_permission(request, self.view))

        # Admin group user (should be false for strict moderator permission)
        request = self.factory.get("/")
        request.user = self.admin_user
        self.assertFalse(permission.has_permission(request, self.view))

        # Moderator user
        request = self.factory.get("/")
        request.user = self.moderator_user
        self.assertTrue(permission.has_permission(request, self.view))

    def test_is_admin_or_moderator_role(self):
        permission = IsAdminOrModeratorRole()

        # Unauthenticated
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.assertFalse(permission.has_permission(request, self.view))

        # Regular user
        request = self.factory.get("/")
        request.user = self.regular_user
        self.assertFalse(permission.has_permission(request, self.view))

        # Moderator user
        request = self.factory.get("/")
        request.user = self.moderator_user
        self.assertTrue(permission.has_permission(request, self.view))

        # Admin group user
        request = self.factory.get("/")
        request.user = self.admin_user
        self.assertTrue(permission.has_permission(request, self.view))

        # Staff user
        request = self.factory.get("/")
        request.user = self.staff_user
        self.assertTrue(permission.has_permission(request, self.view))


from apps.accounts.views import UserListView
from rest_framework.test import force_authenticate


class UserListViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = UserListView.as_view()

        # Create groups
        self.admin_group = Group.objects.create(name="Admin")
        self.moderator_group = Group.objects.create(name="Moderator")

        # Create users
        self.regular_user = User.objects.create_user(
            username="regular2", password="password"
        )

        self.admin_user = User.objects.create_user(
            username="admin2", password="password"
        )
        self.admin_user.groups.add(self.admin_group)

        self.moderator_user = User.objects.create_user(
            username="moderator2", password="password"
        )
        self.moderator_user.groups.add(self.moderator_group)

        self.staff_user = User.objects.create_user(
            username="staff2", password="password", is_staff=True
        )

    def test_user_list_view_unauthenticated(self):
        request = self.factory.get("/api/accounts/users/")
        response = self.view(request)
        # Should be 401 Unauthorized because of IsAuthenticated
        self.assertEqual(response.status_code, 401)

    def test_user_list_view_regular_user(self):
        request = self.factory.get("/api/accounts/users/")
        force_authenticate(request, user=self.regular_user)
        response = self.view(request)
        # Should be 403 Forbidden because they are not Admin or Moderator
        self.assertEqual(response.status_code, 403)

    def test_user_list_view_moderator(self):
        request = self.factory.get("/api/accounts/users/")
        force_authenticate(request, user=self.moderator_user)
        response = self.view(request)
        # Should be 200 OK
        self.assertEqual(response.status_code, 200)

    def test_user_list_view_admin(self):
        request = self.factory.get("/api/accounts/users/")
        force_authenticate(request, user=self.admin_user)
        response = self.view(request)
        # Should be 200 OK
        self.assertEqual(response.status_code, 200)

    def test_user_list_view_staff(self):
        request = self.factory.get("/api/accounts/users/")
        force_authenticate(request, user=self.staff_user)
        response = self.view(request)
        # Should be 200 OK
        self.assertEqual(response.status_code, 200)
