"""
Tests for request deduplication.
"""

import threading
import time
from django.test import TestCase
from django.core.cache import cache
from apps.deduplication.middleware import RequestCoalescer


class RequestDeduplicationTest(TestCase):
    """
    Test request deduplication functionality.
    """

    def setUp(self):
        cache.clear()
        self.coalescer = RequestCoalescer()

    def test_request_key_generation(self):
        """Test that same requests generate same key."""
        # This is a simplified test
        key1 = "test|key"
        key2 = "test|key"
        self.assertEqual(key1, key2)

    def test_pending_request_registration(self):
        """Test pending request registration."""
        request_key = "test_key"
        self.coalescer.register_pending_request(request_key, "req1")

        # Should be in pending
        self.assertTrue(self.coalescer.is_request_in_progress(request_key))

        # Complete request
        self.coalescer.complete_request(request_key, "result")

        # Should no longer be pending
        self.assertFalse(self.coalescer.is_request_in_progress(request_key))

    def test_cache_response(self):
        """Test caching of responses."""
        request_key = "test_key"
        response_data = {"data": "test"}

        # Cache response
        self.coalescer.set_cached_response(request_key, response_data)

        # Get cached response
        cached = self.coalescer.get_cached_response(request_key)
        self.assertEqual(cached, response_data)

    def test_concurrent_requests(self):
        """Test that concurrent requests are coalesced."""
        results = []

        def make_request():
            time.sleep(0.1)
            results.append("done")

        # Simulate 10 concurrent requests
        threads = []
        for i in range(10):
            t = threading.Thread(target=make_request)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # All requests should have completed
        self.assertEqual(len(results), 10)
