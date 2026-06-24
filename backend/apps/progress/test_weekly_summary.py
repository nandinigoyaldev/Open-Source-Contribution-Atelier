import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from apps.content.models import Lesson
from apps.progress.models import LessonProgress, Badge, UserBadge
from apps.progress.tasks import send_weekly_progress_summary

User = get_user_model()

@pytest.fixture
def mock_users():
    u1 = User.objects.create_user(username="active_user", email="active@example.com")
    u2 = User.objects.create_user(username="inactive_user", email="inactive@example.com")
    return u1, u2

@pytest.fixture
def mock_lesson():
    return Lesson.objects.create(
        slug="test-lesson",
        title="Test Lesson",
        difficulty="beginner"
    )

@pytest.fixture
def mock_badge():
    return Badge.objects.create(
        name="Test Badge",
        slug="test-badge"
    )

@pytest.mark.django_db
@patch("apps.progress.tasks.current_app.send_task")
def test_send_weekly_progress_summary_active_user(mock_send_task, mock_users, mock_lesson, mock_badge):
    """
    Test that an active user gets an email with correct progress aggregated 
    for the last 7 days.
    """
    active_user, inactive_user = mock_users
    now = timezone.now()

    # Create progress within last 7 days for active user
    LessonProgress.objects.create(
        user=active_user,
        lesson=mock_lesson,
        completed=True,
        score=20,
        # Default auto_now will be now
    )
    
    # Create badge within last 7 days for active user
    UserBadge.objects.create(
        user=active_user,
        badge=mock_badge,
        # Default auto_now_add will be now
    )

    # Run the task
    mock_send_task.reset_mock()
    send_weekly_progress_summary()

    # Verify the payload
    bulk_email_calls = [
        call for call in mock_send_task.call_args_list 
        if call.args[0] == "tasks.send_bulk_email"
    ]
    assert len(bulk_email_calls) == 1
    
    call_kwargs = bulk_email_calls[0].kwargs
    task_kwargs = call_kwargs.get("kwargs", {})
    payload = task_kwargs.get("payload")
    
    assert payload is not None
    assert payload["template_id"] == "weekly_progress_summary"
    assert payload["recipients"] == [active_user.email]
    
    data = payload["data"]
    assert data["username"] == "active_user"
    assert data["lessons_completed"] == 1
    assert data["xp_earned"] == 20
    assert data["badges_earned"] == 1
    assert data["badge_names"] == ["Test Badge"]

@pytest.mark.django_db
@patch("apps.progress.tasks.current_app.send_task")
def test_send_weekly_progress_summary_inactive_user(mock_send_task, mock_users, mock_lesson, mock_badge):
    """
    Test that users with no activity (or activity outside 7 days) do not get an email.
    """
    active_user, inactive_user = mock_users

    # Create progress OLDER than 7 days
    old_date = timezone.now() - timedelta(days=10)
    
    with patch("django.utils.timezone.now", return_value=old_date):
        lp = LessonProgress.objects.create(
            user=inactive_user,
            lesson=mock_lesson,
            completed=True,
            score=50,
        )
        # auto_now updates on save, so we override it explicitly
        LessonProgress.objects.filter(pk=lp.pk).update(updated_at=old_date)

        ub = UserBadge.objects.create(
            user=inactive_user,
            badge=mock_badge,
        )
        UserBadge.objects.filter(pk=ub.pk).update(earned_at=old_date)

    # Run the task
    mock_send_task.reset_mock()
    send_weekly_progress_summary()

    # Should not send any bulk emails since the progress is 10 days old
    bulk_email_calls = [
        call for call in mock_send_task.call_args_list 
        if call.args and call.args[0] == "tasks.send_bulk_email"
    ]
    assert len(bulk_email_calls) == 0
