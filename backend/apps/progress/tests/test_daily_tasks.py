import pytest
from apps.content.models import Exercise, Lesson
from apps.progress.models import (
    CodeSubmission,
    DailyTaskRecord,
    LessonProgress,
    PeerReview,
    QuizAttempt,
)
from django.contrib.auth.models import User
from django.utils import timezone


@pytest.mark.django_db
class TestDailyTasks:
    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="password")

    @pytest.fixture
    def other_user(self):
        return User.objects.create_user(username="otheruser", password="password")

    @pytest.fixture
    def lesson(self):
        return Lesson.objects.create(slug="test-lesson", title="Test Lesson")

    def test_lesson_daily_task(self, user, lesson):
        # Initial complete
        LessonProgress.objects.create(
            user=user, lesson=lesson, completed=True, score=100
        )
        record = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record.lessons_completed == 1
        assert not record.lessons_awarded
        assert record.xp_earned == 0

        # Complete second lesson
        lesson2 = Lesson.objects.create(slug="test-lesson-2", title="Test Lesson 2")
        LessonProgress.objects.create(
            user=user, lesson=lesson2, completed=True, score=100
        )

        record.refresh_from_db()
        assert record.lessons_completed == 2
        assert record.lessons_awarded
        assert record.xp_earned == 20

    def test_pr_daily_task(self, user, other_user):
        submission = CodeSubmission.objects.create(
            user=other_user, title="Test PR", code_snippet="print(1)"
        )
        PeerReview.objects.create(
            submission=submission, reviewer=user, feedback="Good", rating=5
        )

        record = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record.prs_reviewed == 1
        assert record.prs_awarded
        assert record.xp_earned == 15

    def test_quiz_daily_task(self, user):
        QuizAttempt.objects.create(
            user=user,
            question_id="q1",
            is_correct=True,
            selected_answer="A",
            correct_answer="A",
        )

        record = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record.quizzes_passed == 1
        assert record.quizzes_awarded
        assert record.xp_earned == 10

    def test_api_view(self, user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)

        # Complete 1 quiz to trigger the quiz task
        QuizAttempt.objects.create(
            user=user,
            question_id="q1",
            is_correct=True,
            selected_answer="A",
            correct_answer="A",
        )

        response = client.get("/api/progress/daily-tasks/")
        assert response.status_code == 200
        data = response.json()

        assert "tasks" in data
        tasks = {t["id"]: t for t in data["tasks"]}

        assert tasks["quizzes"]["completed"] is True
        assert tasks["quizzes"]["current"] == 1

        assert tasks["lessons"]["completed"] is False
        assert tasks["lessons"]["current"] == 0

    def test_edge_case_double_awarding(self, user, lesson):
        # Completing more than the threshold should not double award XP
        LessonProgress.objects.create(
            user=user, lesson=lesson, completed=True, score=100
        )
        lesson2 = Lesson.objects.create(slug="l2", title="l2")
        LessonProgress.objects.create(
            user=user, lesson=lesson2, completed=True, score=100
        )
        lesson3 = Lesson.objects.create(slug="l3", title="l3")
        LessonProgress.objects.create(
            user=user, lesson=lesson3, completed=True, score=100
        )

        record = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record.lessons_completed == 3
        assert record.lessons_awarded is True
        assert record.xp_earned == 20  # Still only 20, not 40

    def test_edge_case_incorrect_quiz_no_award(self, user):
        # Failed quiz should not increment quizzes_passed
        QuizAttempt.objects.create(
            user=user,
            question_id="q2",
            is_correct=False,
            selected_answer="B",
            correct_answer="A",
        )

        # record might not even exist if no correct quizzes or other tasks
        record = DailyTaskRecord.objects.filter(
            user=user, date=timezone.localdate()
        ).first()
        if record:
            assert record.quizzes_passed == 0
        else:
            assert True  # No record created, which is also fine

    def test_edge_case_lesson_recompletion(self, user, lesson):
        # Re-saving a completed lesson should not increment the counter again
        lp = LessonProgress.objects.create(
            user=user, lesson=lesson, completed=True, score=100
        )
        record = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record.lessons_completed == 1

        # Save again (simulating an update like base_score changing)
        lp.score = 200
        lp.save(update_fields=["score"])

        record.refresh_from_db()
        assert record.lessons_completed == 1  # Still 1

    def test_edge_case_cross_day_boundary(self, user, other_user):
        import datetime

        yesterday = timezone.localdate() - datetime.timedelta(days=1)

        # Simulate yesterday's task
        record_yesterday = DailyTaskRecord.objects.create(
            user=user, date=yesterday, prs_reviewed=1, prs_awarded=True, xp_earned=15
        )

        # Today's PR review
        submission = CodeSubmission.objects.create(
            user=other_user, title="PR", code_snippet="print(2)"
        )
        PeerReview.objects.create(
            submission=submission, reviewer=user, feedback="Good", rating=5
        )

        record_today = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record_today.prs_reviewed == 1
        assert record_today.prs_awarded is True
        assert record_today.xp_earned == 15

        # Yesterday's record should be untouched
        record_yesterday.refresh_from_db()
        assert record_yesterday.prs_reviewed == 1
        assert record_yesterday.xp_earned == 15

    def test_edge_case_lesson_recompletion_no_update_fields(self, user, lesson):
        lp = LessonProgress.objects.create(
            user=user, lesson=lesson, completed=True, score=100
        )
        record = DailyTaskRecord.objects.get(user=user, date=timezone.localdate())
        assert record.lessons_completed == 1

        # Save again without update_fields
        lp.score = 300
        lp.save()

        record.refresh_from_db()
        assert (
            record.lessons_completed == 1
        )  # Should still be 1 if signal handles it correctly
