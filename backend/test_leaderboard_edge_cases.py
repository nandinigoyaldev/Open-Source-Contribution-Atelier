import os
import sys
import django
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.progress.services.leaderboard_service import LeaderboardService, get_redis_client

def run_tests():
    test_client = get_redis_client()
    if not test_client:
        print("No redis client available for testing")
        sys.exit(1)

    print("Cleaning up test keys...")
    keys_to_clear = [
        LeaderboardService.ALL_TIME,
        LeaderboardService.get_weekly_key(),
        LeaderboardService.get_monthly_key(),
        LeaderboardService.get_seasonal_key("summer_2026"),
        "leaderboard:users"
    ]
    for k in keys_to_clear:
        test_client.delete(k)

    print("Test 1: Adding custom test data...")
    LeaderboardService.update_user_xp(1, "alice", 150)
    LeaderboardService.update_user_xp(2, "bob", 300)
    LeaderboardService.update_user_xp(3, "charlie", 50)
    LeaderboardService.update_user_xp(4, "dave", 200)
    LeaderboardService.update_user_xp(5, "eve", 200)  # Tie condition

    print("Test 2: Retrieving paginated leaderboard...")
    lb_page1 = LeaderboardService.get_leaderboard("all_time", page=1, limit=3)
    assert lb_page1["total_users"] == 5, f"Expected 5, got {lb_page1['total_users']}"
    assert len(lb_page1["leaderboard"]) == 3, "Expected 3 users on page 1"
    assert lb_page1["leaderboard"][0]["username"] == "bob", "Bob should be #1"
    assert lb_page1["leaderboard"][0]["xp"] == 300
    
    lb_page2 = LeaderboardService.get_leaderboard("all_time", page=2, limit=3)
    assert len(lb_page2["leaderboard"]) == 2, "Expected 2 users on page 2"
    assert lb_page2["leaderboard"][1]["username"] == "charlie"

    print("Test 3: Searching for existing user...")
    search_dave = LeaderboardService.get_leaderboard("all_time", search_username="dave")
    assert search_dave["total_users"] == 5
    assert len(search_dave["leaderboard"]) == 1
    assert search_dave["leaderboard"][0]["username"] == "dave"

    print("Test 4: Searching for non-existing user...")
    search_ghost = LeaderboardService.get_leaderboard("all_time", search_username="ghost")
    assert search_ghost["total_users"] == 5
    assert len(search_ghost["leaderboard"]) == 0

    print("Test 5: Handling Redis failure fallback...")
    with patch('apps.progress.services.leaderboard_service.get_redis_client', return_value=None):
        fallback = LeaderboardService.get_leaderboard("all_time")
        assert fallback == {"total_users": 0, "leaderboard": []}, f"Got {fallback}"

    print("Test 6: User rank lookup...")
    charlie_rank = LeaderboardService.get_user_rank("charlie")
    assert charlie_rank["rank"] == 5
    assert charlie_rank["xp"] == 50

    print("All edge case tests passed successfully \u2728")

if __name__ == "__main__":
    run_tests()
