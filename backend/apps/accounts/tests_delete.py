import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AccountDeletionRequest
from apps.audit.models import AuditEvent
from apps.billing.models import CustomerSubscription, SubscriptionPlan
from apps.chat.models import Message
from apps.content.models import Comment, Lesson
from apps.notes.models import Note
from apps.organizations.models import Organization, OrganizationMembership
from apps.progress.models import Certificate

User = get_user_model()


class SecureAccountDeleteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="john_doe", email="john@example.com", password="pass"
        )
        self.lesson = Lesson.objects.create(
            title="Test", slug="test", content="content"
        )

        # PII data
        Note.objects.create(
            user=self.user, title="My Note", encrypted_content="enc", iv="iv"
        )
        Certificate.objects.create(user=self.user, course_name="Open Source")

        # Public data
        Comment.objects.create(
            user=self.user, lesson=self.lesson, content="Great lesson!"
        )
        Message.objects.create(user=self.user, room_id="general", content="Hello world")

    def test_secure_deletion(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.delete("/api/auth/me/delete/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify user is deleted
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="john_doe")

        # Verify PII is deleted (due to CASCADE)
        self.assertEqual(Note.objects.count(), 0)
        self.assertEqual(Certificate.objects.count(), 0)

        # Verify public contributions are anonymized, not deleted
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)

        comment = Comment.objects.first()
        message = Message.objects.first()

        self.assertEqual(comment.user.username, "anonymous_contributor")
        self.assertEqual(message.user.username, "anonymous_contributor")
        self.assertFalse(comment.user.is_active)

    def test_deletion_with_no_contributions_or_pii(self):
        empty_user = User.objects.create_user(
            username="ghost", email="ghost@example.com", password="pass"
        )
        self.client.force_authenticate(user=empty_user)

        response = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="ghost")

    def test_repeated_deletion_attempt(self):
        self.client.force_authenticate(user=self.user)
        response1 = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response1.status_code, status.HTTP_204_NO_CONTENT)

        response2 = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response2.status_code, status.HTTP_204_NO_CONTENT)

    def test_deletion_preview(self):
        """Users receive preview of dependencies, retention policies, and erasable data."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/me/delete/preview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["can_delete"])
        self.assertEqual(response.data["blocking_dependencies"], [])
        self.assertTrue(len(response.data["retention_exceptions"]) >= 2)
        self.assertTrue(len(response.data["erasable_scope"]) >= 4)
        self.assertEqual(response.data["grace_period_days"], 7)

    def test_organization_sole_owner_blocks_deletion(self):
        """Prevent deletion from silently orphaning owned organizations."""
        org = Organization.objects.create(name="Acme Corp")
        OrganizationMembership.objects.create(
            organization=org, user=self.user, role=OrganizationMembership.ROLE_OWNER
        )

        self.client.force_authenticate(user=self.user)

        # Preview should show cannot delete
        preview = self.client.get("/api/auth/me/delete/preview/")
        self.assertFalse(preview.data["can_delete"])
        self.assertEqual(preview.data["blocking_dependencies"][0]["type"], "organization_sole_owner")

        # Immediate DELETE attempt must be blocked
        response = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocking_dependencies", response.data)

        # POST attempt must also be blocked
        post_resp = self.client.post("/api/auth/me/delete/", {})
        self.assertEqual(post_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_active_subscription_blocks_deletion(self):
        """Prevent deletion from orphaning active paid subscriptions."""
        plan = SubscriptionPlan.objects.create(
            name="Pro Tier", stripe_price_id="price_123", price=29.99
        )
        CustomerSubscription.objects.create(
            user=self.user,
            plan=plan,
            stripe_customer_id="cus_123",
            active=True,
            status="active",
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["blocking_dependencies"][0]["type"], "active_subscription")

    def test_grace_period_schedule_and_cancellation(self):
        """Test scheduling account deletion with grace period and cancelling it."""
        self.client.force_authenticate(user=self.user)

        # Schedule deletion
        sched_resp = self.client.post("/api/auth/me/delete/", {"reason": "Taking a break"})
        self.assertEqual(sched_resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(sched_resp.data["status"], "pending")

        # Verify deletion request exists
        del_req = AccountDeletionRequest.objects.get(user=self.user, status="pending")
        self.assertEqual(del_req.reason, "Taking a break")

        # Cancel during grace period
        cancel_resp = self.client.post("/api/auth/me/delete/cancel/")
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)

        del_req.refresh_from_db()
        self.assertEqual(del_req.status, "cancelled")

        # User is still active and existing
        self.assertTrue(User.objects.filter(username="john_doe").exists())

    def test_audit_event_retention(self):
        """Audit events are retained for compliance with personal actor severed."""
        audit_event = AuditEvent.objects.create(
            actor=self.user,
            action="created",
            resource_type="Lesson",
            resource_id="test",
            before={},
            after={"action": "completed_lesson"},
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Audit event still exists in database
        audit_event.refresh_from_db()
        self.assertIsNone(audit_event.actor)
        self.assertEqual(audit_event.action, "created")
