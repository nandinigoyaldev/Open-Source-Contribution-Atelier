import os
import json
import logging
import redis
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")
    try:
        # Check if we can connect
        client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


class LeaderboardService:
    ALL_TIME = "leaderboard:all_time"

    @staticmethod
    def get_weekly_key(date=None):
        if date is None:
            date = timezone.now()
        return f"leaderboard:weekly:{date.strftime('%Y_%W')}"

    @staticmethod
    def get_monthly_key(date=None):
        if date is None:
            date = timezone.now()
        return f"leaderboard:monthly:{date.strftime('%Y_%m')}"

    @staticmethod
    def get_seasonal_key(season_name):
        return f"leaderboard:seasonal:{season_name}"

    @classmethod
    def update_user_xp(cls, user_id: int, username: str, xp_delta: int):
        client = get_redis_client()
        if not client:
            return

        pipeline = client.pipeline()

        # Ensure we can map username to user_id
        pipeline.hset("leaderboard:users", username, user_id)

        # Update sets
        pipeline.zincrby(cls.ALL_TIME, xp_delta, username)
        pipeline.zincrby(cls.get_weekly_key(), xp_delta, username)
        pipeline.zincrby(cls.get_monthly_key(), xp_delta, username)
        # Seasonal logic could be driven by an active season, for now let's assume a default season
        pipeline.zincrby(cls.get_seasonal_key("summer_2026"), xp_delta, username)

        results = pipeline.execute()

        new_xp_all_time = results[1]

        # Broadcast via WebSockets
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "leaderboard",
                {
                    "type": "leaderboard_update",
                    "event": "xp_update",
                    "user_id": user_id,
                    "username": username,
                    "xp": new_xp_all_time,
                    "message": f"User {username} gained XP",
                },
            )

    @classmethod
    def get_leaderboard(
        cls, time_period="all_time", page=1, limit=50, search_username=None
    ):
        client = get_redis_client()
        if not client:
            return {"total_users": 0, "leaderboard": []}

        if time_period == "weekly":
            key = cls.get_weekly_key()
        elif time_period == "monthly":
            key = cls.get_monthly_key()
        elif time_period.startswith("seasonal"):
            key = cls.get_seasonal_key("summer_2026")
        else:
            key = cls.ALL_TIME

        if search_username:
            rank = client.zrevrank(key, search_username)
            if rank is not None:
                score = client.zscore(key, search_username)
                return {
                    "total_users": client.zcard(key),
                    "leaderboard": [
                        {
                            "username": search_username,
                            "rank": rank + 1,
                            "xp": score,
                            "is_top_3": rank < 3,
                        }
                    ]
                }
            return {"total_users": client.zcard(key), "leaderboard": []}

        start = (page - 1) * limit
        end = start + limit - 1

        results = client.zrevrange(key, start, end, withscores=True)
        total_users = client.zcard(key)

        leaderboard = []
        for i, (username, score) in enumerate(results):
            rank = start + i + 1
            leaderboard.append(
                {"username": username, "rank": rank, "xp": score, "is_top_3": rank <= 3}
            )

        return {"total_users": total_users, "leaderboard": leaderboard}

    @classmethod
    def get_user_rank(cls, username: str, time_period="all_time"):
        client = get_redis_client()
        if not client:
            return None

        if time_period == "weekly":
            key = cls.get_weekly_key()
        elif time_period == "monthly":
            key = cls.get_monthly_key()
        elif time_period.startswith("seasonal"):
            key = cls.get_seasonal_key("summer_2026")
        else:
            key = cls.ALL_TIME

        rank = client.zrevrank(key, username)
        if rank is not None:
            score = client.zscore(key, username)
            return {
                "username": username,
                "rank": rank + 1,
                "xp": score,
                "is_top_3": rank < 3,
            }
        return None
