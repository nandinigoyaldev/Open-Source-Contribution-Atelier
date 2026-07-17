from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
import json
import os

from apps.audit.models import AuditEvent
from apps.audit.middleware import AuditContextMiddleware, _audit_ctx
from apps.audit.tasks import archive_audit_events
from apps.content.models import Lesson

User = get_user_model()


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
            events = AuditEvent.objects.filter(resource_id=str(lesson_id))
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
            events = AuditEvent.objects.filter(resource_id=str(lesson_id)).order_by(
                "created_at"
            )
            self.assertEqual(events.count(), 2)
            updated_event = events[1]
            self.assertEqual(updated_event.action, "updated")
            self.assertEqual(updated_event.before["title"], "Intro to Git")
            self.assertEqual(updated_event.after["title"], "Intro to Git (Updated)")

            # Delete the lesson
            lesson.delete()

            # Verify deleted event
            events = AuditEvent.objects.filter(resource_id=str(lesson_id)).order_by(
                "created_at"
            )
            self.assertEqual(events.count(), 3)
            deleted_event = events[2]
            self.assertEqual(deleted_event.action, "deleted")
            self.assertIsNone(deleted_event.after)
            self.assertEqual(deleted_event.before["title"], "Intro to Git (Updated)")

        middleware = AuditContextMiddleware(view)
        middleware(request)

    def test_archive_audit_events_task(self):
        """archive_audit_events task archives old events and deletes them from DB."""
        # Config custom test archive path
        test_archive_dir = os.path.join(os.path.dirname(__file__), "test_archives")
        self.assertFalse(os.path.exists(test_archive_dir))

        with self.settings(AUDIT_RETENTION_DAYS=1, AUDIT_ARCHIVE_DIR=test_archive_dir):
            # Create a recent event
            AuditEvent.objects.create(
                action="created",
                resource_type="content.lesson",
                resource_id="101",
                created_at=timezone.now(),
            )
            # Create an old event to be archived
            old_time = timezone.now() - timedelta(days=2)
            AuditEvent.objects.create(
                action="created",
                resource_type="content.lesson",
                resource_id="102",
                created_at=old_time,
            )

            self.assertEqual(AuditEvent.objects.count(), 2)

            # Run the archival task
            deleted_count = archive_audit_events()
            self.assertEqual(deleted_count, 1)

            # Assert only recent remains in DB
            self.assertEqual(AuditEvent.objects.count(), 1)
            self.assertEqual(AuditEvent.objects.first().resource_id, "101")

            # Assert archive JSON file was written
            files = os.listdir(test_archive_dir)
            self.assertEqual(len(files), 1)
            archive_path = os.path.join(test_archive_dir, files[0])
            with open(archive_path, "r") as f:
                data = json.load(f)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["resource_id"], "102")

            # Cleanup file and directory
            os.remove(archive_path)
            os.rmdir(test_archive_dir)

    def test_replay_events_management_command(self):
        """replay_events command successfully rebuilds Lesson state."""
        # Create a Lesson and save it, generating audit logs
        lesson = Lesson.objects.create(
            title="Old Title",
            slug="old-slug",
            summary="Summary",
            content="Content",
            difficulty="beginner",
        )
        lesson_id = lesson.id

        # Modify and delete, producing the audit trail
        lesson.title = "Replayed Title"
        lesson.save()
        lesson.delete()

        self.assertFalse(Lesson.objects.filter(id=lesson_id).exists())

        # Verify we have created, updated, deleted events
        self.assertEqual(
            AuditEvent.objects.filter(resource_id=str(lesson_id)).count(), 3
        )

        # Run replay command
        from_str = (timezone.now() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        to_str = (timezone.now() + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")

        call_command(
            "replay_events",
            f"--from={from_str}",
            f"--to={to_str}",
            "--resource-type=lesson",
        )

        # It should end up in the last state (deleted) because we replayed a delete event at the end.
        self.assertFalse(Lesson.objects.filter(id=lesson_id).exists())

        # Let's test a replay excluding the delete event (by deleting the audit event for deletion or just replaying created/updated)
        # But AuditEvents are immutable! We can't delete them easily through instance.delete(), but we can do a QuerySet delete.
        AuditEvent.objects.filter(resource_id=str(lesson_id), action="deleted").delete()

        call_command(
            "replay_events",
            f"--from={from_str}",
            f"--to={to_str}",
            "--resource-type=lesson",
        )

        # Now the lesson should be rebuilt to the updated title state
        rebuilt = Lesson.objects.get(id=lesson_id)
        self.assertEqual(rebuilt.title, "Replayed Title")
