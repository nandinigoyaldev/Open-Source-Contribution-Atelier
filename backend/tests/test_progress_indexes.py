import pytest
from django.contrib.auth.models import User

from apps.content.models import Lesson
from apps.progress.models import LessonProgress


@pytest.mark.django_db
class TestLessonProgressIndexes:
    """Verify that LessonProgress Meta defines the expected indexes and constraints."""

    def _get_model_index_names(self):
        return [idx.name for idx in LessonProgress._meta.indexes]

    def _get_model_constraint_names(self):
        return [c.name for c in LessonProgress._meta.constraints]

    def test_unique_user_lesson_constraint_exists(self):
        constraint_names = self._get_model_constraint_names()
        assert "unique_user_lesson_progress" in constraint_names

    def test_user_completed_index_exists(self):
        index_names = self._get_model_index_names()
        assert "idx_progress_user_completed" in index_names

    def test_user_score_index_exists(self):
        index_names = self._get_model_index_names()
        assert "idx_progress_user_score" in index_names

    def test_unique_constraint_enforced(self):
        """Inserting a duplicate (user, lesson) pair raises IntegrityError."""
        user = User.objects.create_user(username="dup_user")
        lesson = Lesson.objects.create(
            title="Dup Lesson",
            slug="dup-lesson",
            summary="s",
            content="c",
            order=1,
        )
        LessonProgress.objects.create(user=user, lesson=lesson, completed=False)

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            # completed differs intentionally — uniqueness is on (user, lesson) alone
            LessonProgress.objects.create(user=user, lesson=lesson, completed=True)

    def test_no_unique_together_on_meta(self):
        """Confirm the deprecated unique_together has been removed."""
        assert LessonProgress._meta.unique_together == ()
