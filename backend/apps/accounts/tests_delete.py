import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.chat.models import Message
from apps.content.models import Comment, Lesson
from apps.notes.models import Note
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
        # Create a fresh user with nothing attached (except auto-created profile)
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

        # Second attempt should fail as the user is already deleted,
        # though force_authenticate bypasses standard auth checks,
        # request.user.delete() will just affect 0 rows or error if not handled.
        # But actually request.user still holds the in-memory object.
        # Calling delete() again won't crash Django, it just deletes 0 rows.
        response2 = self.client.delete("/api/auth/me/delete/")
        self.assertEqual(response2.status_code, status.HTTP_204_NO_CONTENT)
