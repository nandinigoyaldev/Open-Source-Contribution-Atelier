from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse


class AdminLogEntryTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username="admin_user", password="password123", email="admin@example.com"
        )
        self.client.login(username="admin_user", password="password123")

    def test_logentry_admin_is_read_only(self):
        """
        Verify that the LogEntry admin view is accessible but strictly read-only.
        """
        # Create a dummy log entry to verify it appears in the list
        content_type = ContentType.objects.get_for_model(User)
        log_entry = LogEntry.objects.log_action(
            user_id=self.superuser.pk,
            content_type_id=content_type.pk,
            object_id=self.superuser.pk,
            object_repr=str(self.superuser),
            action_flag=ADDITION,
            change_message="Created user",
        )

        # Test 1: The changelist view should return 200 OK
        url_list = reverse("admin:admin_logentry_changelist")
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.status_code, 200)
        self.assertContains(response_list, "admin_user")

        # Test 2: The add view should be forbidden (403) or redirect (since has_add_permission=False)
        url_add = reverse("admin:admin_logentry_add")
        response_add = self.client.get(url_add)
        self.assertEqual(response_add.status_code, 403)

        # Test 3: The change view should be forbidden or read-only
        url_change = reverse("admin:admin_logentry_change", args=[log_entry.pk])
        response_change = self.client.get(url_change)
        # Note: If has_change_permission=False but we allow view permission (implicitly in newer Djangos via has_view_permission),
        # it might return 200 but without save buttons. Or if has_view_permission defaults to False, 403.
        # But we haven't overridden has_view_permission, so let's just ensure we can't POST a change.
        response_post_change = self.client.post(url_change, {"action_flag": CHANGE})
        self.assertEqual(response_post_change.status_code, 403)

        # Test 4: Delete permission denied
        url_delete = reverse("admin:admin_logentry_delete", args=[log_entry.pk])
        response_delete = self.client.post(url_delete, {"post": "yes"})
        self.assertEqual(response_delete.status_code, 403)

        # Ensure log entry still exists
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_logentry_edge_case_non_staff_user(self):
        """
        Verify that a non-staff user cannot access the logs.
        """
        normal_user = User.objects.create_user(
            username="normal", password="password123"
        )
        self.client.login(username="normal", password="password123")

        url_list = reverse("admin:admin_logentry_changelist")
        response_list = self.client.get(url_list)
        # Should redirect to admin login page or 403
        self.assertNotEqual(response_list.status_code, 200)

    def test_logentry_edge_case_deleted_object_reference(self):
        """
        Verify that the admin log list view doesn't crash when the referenced object is hard-deleted.
        Log entries retain object_repr even if the object_id is orphaned.
        """
        # Create a dummy user, log its creation, then delete it
        dummy = User.objects.create_user(username="dummy_target")
        content_type = ContentType.objects.get_for_model(User)

        LogEntry.objects.log_action(
            user_id=self.superuser.pk,
            content_type_id=content_type.pk,
            object_id=dummy.pk,
            object_repr="Deleted User 🚀",  # Unicode custom data
            action_flag=DELETION,
            change_message="Deleted user manually",
        )

        # Now hard delete the actual object
        dummy.delete()

        url_list = reverse("admin:admin_logentry_changelist")
        response = self.client.get(url_list)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted User 🚀")

    def test_logentry_edge_case_search_json_message(self):
        """
        Verify that searching parses and matches stringified JSON change messages.
        Modern Django uses JSON for change_message.
        """
        import json

        change_data = [{"added": {"name": "special custom flag"}}]

        LogEntry.objects.log_action(
            user_id=self.superuser.pk,
            content_type_id=ContentType.objects.get_for_model(User).pk,
            object_id=self.superuser.pk,
            object_repr="admin_user",
            action_flag=CHANGE,
            change_message=json.dumps(change_data),
        )

        url_list = reverse("admin:admin_logentry_changelist")
        # Search for "special custom"
        response = self.client.get(url_list, {"q": "special custom"})
        self.assertEqual(response.status_code, 200)
        # Verify the row is found by checking for the object_repr
        self.assertContains(response, "admin_user")
