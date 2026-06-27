from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import Note

User = get_user_model()


class NoteAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username="user1", password="password123")
        self.user2 = User.objects.create_user(username="user2", password="password123")

    def test_unauthenticated_access(self):
        response = self.client.get("/api/notes/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_and_retrieve_note(self):
        self.client.force_authenticate(user=self.user1)

        # Create a note
        data = {
            "title": "My Secret",
            "encrypted_content": "base64ciphertext",
            "iv": "base64iv",
        }
        response = self.client.post("/api/notes/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Note.objects.count(), 1)
        note = Note.objects.first()
        self.assertEqual(note.user, self.user1)
        self.assertEqual(note.encrypted_content, "base64ciphertext")

        # Retrieve notes
        response = self.client.get("/api/notes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "My Secret")

    def test_notes_are_isolated_between_users(self):
        Note.objects.create(
            user=self.user1, title="User 1 Note", encrypted_content="A", iv="1"
        )
        Note.objects.create(
            user=self.user2, title="User 2 Note", encrypted_content="B", iv="2"
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/notes/")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "User 1 Note")

    def test_update_note(self):
        self.client.force_authenticate(user=self.user1)
        note = Note.objects.create(
            user=self.user1, title="Old Title", encrypted_content="Old", iv="OldIV"
        )

        data = {"title": "New Title", "encrypted_content": "New", "iv": "NewIV"}
        response = self.client.put(f"/api/notes/{note.id}/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        note.refresh_from_db()
        self.assertEqual(note.title, "New Title")

    def test_delete_note(self):
        self.client.force_authenticate(user=self.user1)
        note = Note.objects.create(
            user=self.user1, title="Del", encrypted_content="A", iv="1"
        )

        response = self.client.delete(f"/api/notes/{note.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Note.objects.count(), 0)
