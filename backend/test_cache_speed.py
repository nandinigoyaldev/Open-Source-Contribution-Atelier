import os
import sys
import time
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import RequestFactory
from django.core.cache import cache
from apps.search.views import UnifiedSearchView
from unittest.mock import patch


def run_benchmark():
    factory = RequestFactory()
    view = UnifiedSearchView.as_view()

    print("\n[Redis Search Cache Benchmark]")
    print("=" * 40)

    # 1. Clear Cache
    cache.clear()
    print(" Cache cleared.")

    # Mock the database query so SQLite doesn't crash on Postgres functions
    with patch("apps.search.views.UnifiedSearchView.get_queryset") as mock_qs:
        # Mocking an empty queryset return to simulate DB hitting
        mock_qs.return_value = []

        # 2. First Request (Cache Miss)
        print("\n=> Initiating Request 1 (Cache MISS)")
        start_time = time.time()
        request = factory.get("/api/search/", {"q": "Algorithms"})
        response1 = view(request)
        response1.render()  # Evaluate response
        miss_time = (time.time() - start_time) * 1000
        print(f"  Time taken: {miss_time:.2f} ms")

        # 3. Second Request (Cache Hit)
        print("\n=> Initiating Request 2 (Cache HIT)")
        start_time = time.time()
        request = factory.get("/api/search/", {"q": "Algorithms"})
        response2 = view(request)
        response2.render()  # Evaluate response
        hit_time = (time.time() - start_time) * 1000
        print(f"  Time taken: {hit_time:.2f} ms")

        # 4. Performance Improvement
        if hit_time > 0:
            speedup = miss_time / hit_time
            print("\n Results:")
            print(f"Cached response was {speedup:.1f}x faster!")

        # 5. Simulating Cache Invalidation
        print("\n=> Simulating Document Update (Invalidation)")
        from apps.search.utils import bump_search_cache_version

        bump_search_cache_version()

        # 6. Third Request (Cache Miss after invalidation)
        print("\n=> Initiating Request 3 (Post-Invalidation Cache MISS)")
        start_time = time.time()
        request = factory.get("/api/search/", {"q": "Algorithms"})
        response3 = view(request)
        response3.render()  # Evaluate response
        miss_time2 = (time.time() - start_time) * 1000
        print(f"  Time taken: {miss_time2:.2f} ms")

        print("\n Benchmark Complete.")


if __name__ == "__main__":
    run_benchmark()
