import json
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.audit.middleware import AuditContextMiddleware, _audit_ctx
from apps.audit.models import AuditEvent
from apps.audit.tasks import archive_audit_events
from apps.content.models import Lesson

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class AuditTrailTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testadmin", email="test@example.com", password="password"
        )
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

    def test_audit_event_immutability(self):
        """AuditEvent records cannot be updated or deleted."""
        event = AuditEvent.objects.create(
            action="created",
            resource_type="content.lesson",
            resource_id="1",
            after={"title": "Test"},
        )

        # Test update failure
        with self.assertRaises(PermissionError):
            event.action = "updated"
            event.save()

        # Test delete failure
        with self.assertRaises(PermissionError):
            event.delete()

        # Verify it still exists in the DB
        self.assertTrue(AuditEvent.objects.filter(id=event.id).exists())

    def test_middleware_captures_context(self):
        """AuditContextMiddleware correctly populates and clears thread-local context."""
        request = self.factory.get("/api/lessons/")
        request.user = self.user
        request.request_id = "test-correlation-id-123"
        request.META["REMOTE_ADDR"] = "192.168.1.50"
        request.META["HTTP_USER_AGENT"] = "TestAgent"

        def dummy_view(req):
            self.assertEqual(_audit_ctx.actor, self.user)
            self.assertEqual(_audit_ctx.ip_address, "192.168.1.50")
            self.assertEqual(_audit_ctx.user_agent, "TestAgent")
            self.assertEqual(_audit_ctx.correlation_id, "test-correlation-id-123")
            return None

        middleware = AuditContextMiddleware(dummy_view)
        middleware(request)

        # Thread-local should be cleared after request lifecycle
        self.assertIsNone(getattr(_audit_ctx, "actor", None))
        self.assertIsNone(getattr(_audit_ctx, "ip_address", None))

    def test_signals_emit_audit_events(self):
        """Saving/deleting an AuditableModel (Lesson) automatically creates AuditEvents."""
        request = self.factory.post("/api/lessons/")
        request.user = self.user
        request.request_id = "request-id-456"
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Wrap in middleware view lifecycle to populate context
        def view(req):
            lesson = Lesson.objects.create(
                title="Intro to Git",
                slug="intro-to-git",
                summary="Learn Git basics",
                content="Git content...",
                difficulty="beginner",
            )
            lesson_id = lesson.id

            # Verify created event
            events = AuditEvent.objects.filter(
                resource_type="content.lesson", resource_id=str(lesson_id)
            )
            self.assertEqual(events.count(), 1)
            created_event = events.first()
            self.assertEqual(created_event.action, "created")
            self.assertEqual(created_event.actor, self.user)
            self.assertEqual(created_event.correlation_id, "request-id-456")
            self.assertEqual(created_event.ip_address, "127.0.0.1")
            self.assertIsNotNone(created_event.after)
            self.assertEqual(created_event.after["title"], "Intro to Git")

            # Update the lesson
            lesson.title = "Intro to Git (Updated)"
            lesson.save()

            # Verify updated event
            events = AuditEvent.objects.filter(
                resource_type="content.lesson", resource_id=str(lesson_id)
            ).order_by("created_at")
            self.assertEqual(events.count(), 2)
            updated_event = events[1]
            self.assertEqual(updated_event.action, "updated")
            self.assertEqual(updated_event.before["title"], "Intro to Git")
            self.assertEqual(updated_event.after["title"], "Intro to Git (Updated)")

            # Delete the lesson
            lesson.delete()

            # Verify deleted event
            events = AuditEvent.objects.filter(
                resource_type="content.lesson", resource_id=str(lesson_id)
            ).order_by("created_at")
            self.assertEqual(events.count(), 3)
            deleted_event = events[2]
            self.assertEqual(deleted_event.action, "deleted")
            self.assertIsNone(deleted_event.after)
            self.assertEqual(deleted_event.before["title"], "Intro to Git (Updated)")

        middleware = AuditContextMiddleware(view)
        middleware(request)

    def test_archive_audit_events_task(self):
        """archive_audit_events task archives old events and deletes them from DB."""
        test_archive_dir = os.path.join(os.path.dirname(__file__), "test_archives")
        self.assertFalse(os.path.exists(test_archive_dir))

        with self.settings(AUDIT_RETENTION_DAYS=1, AUDIT_ARCHIVE_DIR=test_archive_dir):
            initial_count = AuditEvent.objects.count()
            AuditEvent.objects.create(
                action="created",
                resource_type="content.lesson",
                resource_id="101",
                created_at=timezone.now(),
            )
            old_time = timezone.now() - timedelta(days=2)
            AuditEvent.objects.create(
                action="created",
                resource_type="content.lesson",
                resource_id="102",
                created_at=old_time,
            )

            self.assertEqual(AuditEvent.objects.count(), initial_count + 2)

            deleted_count = archive_audit_events()
            self.assertEqual(deleted_count, 1)

            self.assertEqual(AuditEvent.objects.count(), initial_count + 1)
            self.assertEqual(AuditEvent.objects.first().resource_id, "101")

            files = os.listdir(test_archive_dir)
            self.assertEqual(len(files), 1)
            archive_path = os.path.join(test_archive_dir, files[0])
            with open(archive_path, "r") as f:
                data = json.load(f)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["resource_id"], "102")

            os.remove(archive_path)
            os.rmdir(test_archive_dir)

    def test_replay_events_management_command(self):
        """replay_events command successfully rebuilds Lesson state."""
        lesson = Lesson.objects.create(
            title="Old Title",
            slug="old-slug",
            summary="Summary",
            content="Content",
            difficulty="beginner",
        )
        lesson_id = lesson.id

        lesson.title = "Replayed Title"
        lesson.save()
        lesson.delete()

        self.assertFalse(Lesson.objects.filter(id=lesson_id).exists())
        self.assertGreaterEqual(
            AuditEvent.objects.filter(resource_id=str(lesson_id)).count(), 3
        )

        from_str = (timezone.now() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        to_str = (timezone.now() + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")

        call_command(
            "replay_events",
            f"--from={from_str}",
            f"--to={to_str}",
            "--resource-type=lesson",
        )

        self.assertFalse(Lesson.objects.filter(id=lesson_id).exists())

        AuditEvent.objects.filter(resource_id=str(lesson_id), action="deleted").delete()

        call_command(
            "replay_events",
            f"--from={from_str}",
            f"--to={to_str}",
            "--resource-type=lesson",
        )

        rebuilt = Lesson.objects.get(id=lesson_id)
        self.assertEqual(rebuilt.title, "Replayed Title")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class AuditApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="password123",
            is_staff=True,
        )
        self.normal_user = User.objects.create_user(
            username="normaluser",
            email="normal@example.com",
            password="password123",
            is_staff=False,
        )

        self.event1 = AuditEvent.objects.create(
            actor=self.admin_user,
            action="created",
            resource_type="content.lesson",
            resource_id="1001",
            before=None,
            after={"title": "Lesson 1", "difficulty": "beginner"},
            correlation_id="corr-111",
            ip_address="127.0.0.1",
        )
        self.event2 = AuditEvent.objects.create(
            actor=self.normal_user,
            action="updated",
            resource_type="content.module",
            resource_id="2002",
            before={"title": "Module Old"},
            after={"title": "Module New"},
            correlation_id="corr-222",
            ip_address="192.168.1.1",
        )
        self.event3 = AuditEvent.objects.create(
            actor=self.admin_user,
            action="deleted",
            resource_type="content.lesson",
            resource_id="1001",
            before={"title": "Lesson 1"},
            after=None,
            correlation_id="corr-333",
            ip_address="127.0.0.1",
        )

    def test_permission_required(self):
        """Non-admin user cannot access the audit API."""
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/admin/audit/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated request
        unauth_client = APIClient()
        response = unauth_client.get("/api/admin/audit/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_list_audit_events(self):
        """Admin user can list audit events with pagination and calculated summaries."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/audit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(response.data["count"], 3)

        first_item = response.data["results"][0]
        self.assertIn("summary", first_item)
        self.assertIn("actor_username", first_item)

    def test_search_and_filters(self):
        """Audit events can be filtered by action, actor, resource_type, and search query."""
        self.client.force_authenticate(user=self.admin_user)

        # Filter by action and model_type
        res = self.client.get("/api/admin/audit/?action=created&model_type=lesson")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.event1.id)

        # Filter by model_type / resource_type
        res = self.client.get("/api/admin/audit/?model_type=module")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.event2.id)

        # Filter by actor username
        res = self.client.get("/api/admin/audit/?actor=normaluser")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.event2.id)

        # Structured free-text search
        res = self.client.get("/api/admin/audit/?search=corr-222")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.event2.id)

    def test_audit_detail_view(self):
        """GET /api/admin/audit/<id>/ returns full event detail."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"/api/admin/audit/{self.event2.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["resource_id"], "2002")
        self.assertEqual(response.data["before"], {"title": "Module Old"})
        self.assertEqual(response.data["after"], {"title": "Module New"})

    def test_export_csv(self):
        """GET /api/admin/audit/?export=csv returns downloadable CSV respecting filters."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/audit/?action=created&export=csv")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

        content = b"".join(response.streaming_content).decode("utf-8")
        lines = [line for line in content.splitlines() if line]
        self.assertGreaterEqual(len(lines), 2)  # Header + 1 row
        self.assertIn("Created", lines[1])

    def test_export_json(self):
        """GET /api/admin/audit/?export=json returns downloadable JSON array."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/audit/?export=json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

        data = json.loads(b"".join(response.streaming_content))
        self.assertGreaterEqual(len(data), 3)
