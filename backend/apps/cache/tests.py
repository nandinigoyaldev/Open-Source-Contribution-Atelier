"""
Tests for cache system.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()
from apps.cache.services.cache_manager import CacheManager
from apps.cache.services.write_through_cache import (
    WriteThroughCache,
    WriteThroughCacheManager,
)
from apps.cache.models import CacheDependency


class CacheManagerTest(TestCase):
    """
    Test CacheManager functionality.
    """

    def setUp(self):
        self.manager = CacheManager()
        self.user = User.objects.create_user(username="testuser")

    def test_get_cache_key(self):
        """Test cache key generation."""
        key1 = self.manager.get_cache_key("test", user_id=1)
        key2 = self.manager.get_cache_key("test", user_id=1)

        # Same arguments should generate same key
        self.assertEqual(key1, key2)

        # Different arguments should generate different keys
        key3 = self.manager.get_cache_key("test", user_id=2)
        self.assertNotEqual(key1, key3)

    def test_set_and_get(self):
        """Test setting and getting cache values."""
        key = self.manager.get_cache_key("test", key="value")

        # Set value
        self.manager.set(key, "test_value")

        # Get value
        value = self.manager.get(key)
        self.assertEqual(value, "test_value")

    def test_delete(self):
        """Test deleting cache values."""
        key = self.manager.get_cache_key("test", key="value")

        # Set value
        self.manager.set(key, "test_value")

        # Delete value
        self.manager.delete(key)

        # Get should return None
        value = self.manager.get(key)
        self.assertIsNone(value)

    def test_track_dependency(self):
        """Test tracking dependencies."""
        key = "test:cache:key"
        self.manager.track_dependency(self.user, self.user, key)

        # Check dependency exists
        dependency = CacheDependency.objects.filter(cache_key=key).first()
        self.assertIsNotNone(dependency)

    def test_invalidate_dependencies(self):
        """Test invalidating dependencies."""
        key = "test:cache:key"
        self.manager.track_dependency(self.user, self.user, key)

        # Set cache value
        self.manager.set(key, "test_value")

        # Invalidate dependencies
        self.manager.invalidate_dependencies(self.user)

        # Cache should be cleared
        value = self.manager.get(key)
        self.assertIsNone(value)


class WriteThroughCacheTest(TestCase):
    """
    Test WriteThroughCache functionality.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.cache = WriteThroughCache(User)

    def test_get_create(self):
        """Test getting and creating through cache."""
        # Create user through cache
        user, created = WriteThroughCacheManager.get_or_create(
            User, defaults={"email": "test@example.com"}, username="newuser"
        )

        self.assertTrue(created)
        self.assertEqual(user.username, "newuser")

        # Get existing user through cache
        user2, created2 = WriteThroughCacheManager.get_or_create(
            User, username="newuser"
        )

        self.assertFalse(created2)
        self.assertEqual(user2.id, user.id)
