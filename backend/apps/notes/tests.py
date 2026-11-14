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
        results = (
            response.data.get("results")
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "My Secret")

    def test_notes_are_isolated_between_users(self):
        Note.objects.create(
            user=self.user1, title="User 1 Note", encrypted_content="A", iv="1"
        )
        Note.objects.create(
            user=self.user2, title="User 2 Note", encrypted_content="B", iv="2"
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/notes/")
        results = (
            response.data.get("results")
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "User 1 Note")

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

    def test_two_device_concurrent_edit_conflict(self):
        self.client.force_authenticate(user=self.user1)
        note = Note.objects.create(
            user=self.user1,
            title="Initial Title",
            encrypted_content="Initial Content",
            iv="IV1",
            version=1,
        )

        # Device A updates note with expected_version=1
        dev_a_data = {
            "title": "Device A Title",
            "encrypted_content": "Device A Content",
            "iv": "IVA",
            "expected_version": 1,
        }
        res_a = self.client.put(f"/api/notes/{note.id}/", dev_a_data, format="json")
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        note.refresh_from_db()
        self.assertEqual(note.version, 2)
        self.assertEqual(note.title, "Device A Title")

        # Device B (stale, expected_version=1) tries to update -> HTTP 409 Conflict
        dev_b_data = {
            "title": "Device B Title",
            "encrypted_content": "Device B Content",
            "iv": "IVB",
            "expected_version": 1,
        }
        res_b = self.client.put(f"/api/notes/{note.id}/", dev_b_data, format="json")
        self.assertEqual(res_b.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res_b.data["error"], "conflict")
        self.assertEqual(res_b.data["server_version"], 2)
        self.assertIn("server_data", res_b.data)
        # Verify content was not silently overwritten
        note.refresh_from_db()
        self.assertEqual(note.title, "Device A Title")

    def test_offline_retry_with_client_id_does_not_duplicate(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "title": "Offline Created Note",
            "encrypted_content": "content",
            "iv": "iv",
            "client_id": "client-uuid-12345",
        }
        # First creation attempt
        res1 = self.client.post("/api/notes/", payload, format="json")
        self.assertIn(
            res1.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK]
        )
        self.assertEqual(Note.objects.count(), 1)

        # Replay/Retry of offline queue with same client_id
        res2 = self.client.post("/api/notes/", payload, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(Note.objects.count(), 1)
