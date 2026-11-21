"""
Bookmark writes replayed by the offline queue (issue #3328).

The frontend queues bookmark adds and removals while offline and replays them on
reconnect with an Idempotency-Key, so a replay of a write the server already
applied gets the first answer back instead of a second write (or a 404 for a
delete). A removal also says which bookmark it removes (expected_id), and is
refused with a 409 when the lesson was bookmarked again since.
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.deduplication.models import IdempotencyRecord
from apps.progress.models import LessonBookmark
from apps.progress.views import BOOKMARK_CONFLICT_CODE

User: Any = get_user_model()
Bookmarks: Any = LessonBookmark._default_manager
Lessons: Any = Lesson._default_manager
Records: Any = IdempotencyRecord._default_manager


class BookmarkReplayTests(TestCase):
    def setUp(self) -> None:
        # Throttle counters and idempotency locks live in the cache
        cache.clear()
        self.user = User.objects.create_user(username="reader", password="pw12345!")
        self.lesson = Lessons.create(
            slug="git-basics", title="Git Basics", difficulty="beginner"
        )
        self.client: Any = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/progress/bookmarks/git-basics/"

    def test_replayed_add_returns_the_first_answer(self):
        first = self.client.post(self.url, HTTP_IDEMPOTENCY_KEY="add-1")
        replay = self.client.post(self.url, HTTP_IDEMPOTENCY_KEY="add-1")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.headers.get("Idempotency-Replay"), "true")
        self.assertEqual(Bookmarks.filter(user=self.user).count(), 1)

    def test_replayed_delete_is_not_a_404(self):
        Bookmarks.create(user=self.user, lesson=self.lesson)

        first = self.client.delete(self.url, HTTP_IDEMPOTENCY_KEY="remove-1")
        replay = self.client.delete(self.url, HTTP_IDEMPOTENCY_KEY="remove-1")

        self.assertEqual(first.status_code, 204)
        self.assertEqual(replay.status_code, 204)
        self.assertEqual(replay.headers.get("Idempotency-Replay"), "true")
        self.assertFalse(Bookmarks.filter(user=self.user).exists())

    def test_delete_without_a_key_keeps_the_old_404(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Records.exists())

    def test_removal_does_not_drop_a_bookmark_saved_again(self):
        old = Bookmarks.create(user=self.user, lesson=self.lesson)
        old_id = old.id
        old.delete()
        # Saved again from another device after this client read it
        newer = Bookmarks.create(user=self.user, lesson=self.lesson)

        response = self.client.delete(
            f"{self.url}?expected_id={old_id}",
            HTTP_IDEMPOTENCY_KEY="remove-stale",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], BOOKMARK_CONFLICT_CODE)
        self.assertEqual(response.data["lesson_slug"], "git-basics")
        self.assertTrue(response.data["bookmarked"])
        self.assertEqual(response.data["id"], newer.id)
        self.assertTrue(Bookmarks.filter(pk=newer.pk).exists())

    def test_removal_of_the_bookmark_the_client_saw_goes_through(self):
        bookmark = Bookmarks.create(user=self.user, lesson=self.lesson)

        response = self.client.delete(f"{self.url}?expected_id={bookmark.id}")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Bookmarks.filter(pk=bookmark.pk).exists())

    def test_malformed_expected_id_is_rejected(self):
        bookmark = Bookmarks.create(user=self.user, lesson=self.lesson)

        response = self.client.delete(f"{self.url}?expected_id=latest")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Bookmarks.filter(pk=bookmark.pk).exists())

    def test_keys_are_scoped_to_the_user(self):
        other = User.objects.create_user(username="other", password="pw12345!")
        Bookmarks.create(user=other, lesson=self.lesson)
        self.client.post(self.url, HTTP_IDEMPOTENCY_KEY="shared-key")

        other_client: Any = APIClient()
        other_client.force_authenticate(user=other)
        response = other_client.delete(self.url, HTTP_IDEMPOTENCY_KEY="shared-key")

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.headers.get("Idempotency-Replay"))
        self.assertFalse(Bookmarks.filter(user=other).exists())
        self.assertTrue(Bookmarks.filter(user=self.user).exists())
