import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from apps.progress.streak_engine import StreakEngine
from apps.progress.models import StreakProfile

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="streaker", password="password123")

@pytest.mark.django_db
class TestStreakEngine:
    
    def test_record_activity_first_time(self, test_user):
        """User logs activity for the first time."""
        today = date.today()
        result = StreakEngine.record_activity(test_user, today)
        
        assert result["current_streak"] == 1
        assert result["longest_streak"] == 1
        
        profile = StreakProfile.objects.get(user=test_user)
        assert profile.last_activity_date == today

    def test_record_activity_consecutive_days(self, test_user):
        """User logs activity on two consecutive days."""
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        
        # Day 1
        StreakEngine.record_activity(test_user, yesterday)
        # Day 2
        result = StreakEngine.record_activity(test_user, today)
        
        assert result["current_streak"] == 2
        assert result["longest_streak"] == 2

    def test_record_activity_same_day_idempotent(self, test_user):
        """Logging activity multiple times on the same day shouldn't increase streak."""
        today = date.today()
        
        StreakEngine.record_activity(test_user, today)
        result = StreakEngine.record_activity(test_user, today) # Second time
        
        assert result["current_streak"] == 1

    def test_record_activity_streak_broken(self, test_user):
        """Streak should reset to 1 if a day is skipped."""
        two_days_ago = date.today() - timedelta(days=2)
        today = date.today()
        
        StreakEngine.record_activity(test_user, two_days_ago)
        result = StreakEngine.record_activity(test_user, today) # Gap of 1 day
        
        assert result["current_streak"] == 1
        # Longest streak should still remember the old high score (if it was higher)
        assert result["longest_streak"] == 1

    def test_get_multiplier_for_user(self, test_user):
        """Should return the correct multiplier."""
        assert StreakEngine.get_multiplier_for_user(test_user) == 1.0
        
        StreakEngine.record_activity(test_user, date.today())
        multiplier = StreakEngine.get_multiplier_for_user(test_user)
        assert multiplier >= 1.0

    def test_get_streak_data_api_format(self, test_user):
        """Should return a nicely formatted dict for the API/Views."""
        StreakEngine.record_activity(test_user, date.today())
        data = StreakEngine.get_streak_data(test_user)
        
        assert "current_streak" in data
        assert "longest_streak" in data
        assert "current_multiplier" in data
        assert "milestone_progress_pct" in data
        assert data["current_streak"] == 1