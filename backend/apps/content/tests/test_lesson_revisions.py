"""Versioned lesson publishing with rollback (#3323)."""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.content.models import Lesson, LessonVersion
from apps.progress.models import LessonProgress
from apps.rbac.models import Permission, Role, UserRole

User = get_user_model()


def _user_with(username, *permission_slugs):
    user = User.objects.create_user(username=username, password="pw123456")
    if permission_slugs:
        role = Role.objects.create(name=f"{username}-role")
        for slug in permission_slugs:
            perm, _ = Permission.objects.get_or_create(slug=slug)
            role.permissions.add(perm)
        UserRole.objects.create(user=user, role=role)
    return user


class LessonRevisionWorkflowTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.editor = _user_with("editor", "edit_content")
        self.publisher = _user_with("publisher", "edit_content", "publish_content")
        self.learner = _user_with("learner")
        with self.captureOnCommitCallbacks(execute=True):
            self.lesson = Lesson.objects.create(
                title="Branches",
                slug="branches",
                summary="What a branch is",
                content="original body",
                difficulty="beginner",
            )
        self.progress = LessonProgress.objects.create(
            user=self.learner, lesson=self.lesson, completed=True, score=80
        )
        self.base = f"/api/content/published-lessons/{self.lesson.pk}"

    def _call(self, method: str, path: str, data=None, user=None) -> Any:
        self.api.force_authenticate(user=user)
        with self.captureOnCommitCallbacks(execute=True):
            return getattr(self.api, method)(
                f"{self.base}{path}", data or {}, format="json"
            )

    def _draft(self, content="reviewed body", user=None) -> Any:
        res = self._call(
            "post", "/versions/", {"content": content}, user or self.editor
        )
        self.assertEqual(res.status_code, 201, res.data)
        return res

    def _versions(self):
        return {v.number: v for v in LessonVersion.objects.filter(lesson=self.lesson)}

    def test_direct_save_is_numbered_published_revision(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.lesson.content = "edited body"
            self.lesson.save()
            self.lesson.order = 3  # not part of the snapshot, adds nothing
            self.lesson.save()

        versions = self._versions()
        self.assertEqual(sorted(versions), [1, 2])
        self.assertEqual(versions[1].status, LessonVersion.ARCHIVED)
        self.assertEqual(versions[2].status, LessonVersion.PUBLISHED)
        self.assertEqual(versions[2].content, "edited body")
        self.assertEqual(versions[2].title, "Branches")
        self.assertIsNotNone(versions[2].published_at)

    def test_draft_review_publish_updates_the_same_lesson_row(self):
        draft = self._draft()
        self.assertEqual(draft.data["number"], 2)
        self.assertEqual(draft.data["status"], "draft")
        self.assertEqual(draft.data["authorName"], "editor")
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.content, "original body")

        submitted = self._call("post", "/versions/2/submit/", user=self.editor)
        self.assertEqual(submitted.data["status"], "review")

        denied = self._call("post", "/versions/2/publish/", user=self.editor)
        self.assertEqual(denied.status_code, 403)

        published = self._call("post", "/versions/2/publish/", user=self.publisher)
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(published.data["status"], "published")
        self.assertEqual(published.data["publishedByName"], "publisher")

        lesson = Lesson.objects.get(pk=self.lesson.pk)
        self.assertEqual(lesson.content, "reviewed body")
        versions = self._versions()
        self.assertEqual(sorted(versions), [1, 2])  # publish adds no extra copy
        self.assertEqual(versions[1].status, LessonVersion.ARCHIVED)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.lesson_id, self.lesson.pk)
        self.assertTrue(self.progress.completed)
        self.assertEqual(self.progress.score, 80)

    def test_publish_needs_review_first(self):
        self._draft()

        res = self._call("post", "/versions/2/publish/", user=self.publisher)

        self.assertEqual(res.status_code, 409)
        self.assertEqual(self._versions()[2].status, LessonVersion.DRAFT)

    def test_rollback_writes_a_new_revision_and_leaves_old_ones_alone(self):
        self._draft()
        self._call("post", "/versions/2/submit/", user=self.editor)
        self._call("post", "/versions/2/publish/", user=self.publisher)

        denied = self._call("post", "/rollback/", {"version": 1}, user=self.editor)
        self.assertEqual(denied.status_code, 403)

        res = self._call("post", "/rollback/", {"version": 1}, user=self.publisher)

        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["number"], 3)
        self.assertEqual(res.data["status"], "published")
        self.assertEqual(res.data["restoredFromNumber"], 1)
        self.assertEqual(res.data["note"], "Rollback to v1")
        versions = self._versions()
        self.assertEqual(versions[1].content, "original body")
        self.assertEqual(versions[1].status, LessonVersion.ARCHIVED)
        self.assertEqual(versions[2].content, "reviewed body")
        self.assertEqual(versions[2].status, LessonVersion.ARCHIVED)
        self.assertEqual(versions[3].content, "original body")
        lesson = Lesson.objects.get(pk=self.lesson.pk)
        self.assertEqual(lesson.content, "original body")
        self.assertEqual(LessonProgress.objects.get().lesson_id, self.lesson.pk)

        again = self._call("post", "/rollback/", {"version": 3}, user=self.publisher)
        self.assertEqual(again.status_code, 409)

    def test_rollback_only_to_revisions_that_were_published(self):
        self._draft()
        self._call("post", "/versions/2/archive/", user=self.editor)

        res = self._call("post", "/rollback/", {"version": 2}, user=self.publisher)

        self.assertEqual(res.status_code, 409)
        self.assertEqual(Lesson.objects.get().content, "original body")

    def test_published_revisions_cannot_be_changed_or_deleted(self):
        live = self._versions()[1]

        live.content = "sneaky edit"
        with self.assertRaises(ValidationError):
            live.save()
        live.refresh_from_db()
        live.status = LessonVersion.DRAFT
        with self.assertRaises(ValidationError):
            live.save()
        with self.assertRaises(ValidationError):
            live.delete()
        self.assertEqual(LessonVersion.objects.get(pk=live.pk).content, "original body")

    def test_drafts_are_editable_until_review(self):
        self._draft(content="first try")
        draft = self._versions()[2]
        draft.content = "second try"
        draft.save()

        self._call("post", "/versions/2/submit/", user=self.editor)
        draft.refresh_from_db()
        draft.content = "changed during review"
        with self.assertRaises(ValidationError):
            draft.save()

    def test_learners_only_see_published_history(self):
        self._draft(content="unreviewed idea")

        anon = self._call("get", "/versions/")
        learner = self._call("get", "/versions/", user=self.learner)
        editor = self._call("get", "/versions/", user=self.editor)

        self.assertEqual([v["number"] for v in anon.data], [1])
        self.assertEqual([v["number"] for v in learner.data], [1])
        self.assertEqual([v["number"] for v in editor.data], [2, 1])
        self.assertNotIn("unreviewed idea", str(anon.data))

    def test_history_can_be_looked_up_by_slug(self):
        self.api.force_authenticate(user=None)
        res: Any = self.api.get("/api/content/published-lessons/branches/versions/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual([v["number"] for v in res.data], [1])

    def test_drafts_need_edit_permission(self):
        res = self._call("post", "/versions/", {"content": "x"}, user=self.learner)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(sorted(self._versions()), [1])

    def test_direct_patch_needs_publish_permission_and_credits_author(self):
        editor = self._call("patch", "/", {"content": "hot fix"}, user=self.editor)
        self.assertEqual(editor.status_code, 403)

        res = self._call("patch", "/", {"content": "hot fix"}, user=self.publisher)

        self.assertEqual(res.status_code, 200)
        live = self._versions()[2]
        self.assertEqual(live.status, LessonVersion.PUBLISHED)
        self.assertEqual(live.author, self.publisher)
        self.assertEqual(live.content, "hot fix")
