"""
Cache-Control headers middleware for API GET responses.

Sets appropriate Cache-Control headers on GET responses to allow
browsers (and the service worker) to cache responses and avoid
unnecessary round-trips to the slow HF Spaces backend.
"""


class APICacheControlMiddleware:
    """
    Adds Cache-Control headers to API GET responses based on URL path.

    Must be placed AFTER authentication middleware so it doesn't cache
    responses that vary by user for anonymous users.
    """

    # Mapping of URL path prefixes to max-age values (in seconds)
    CACHE_RULES = {
        "/api/dashboard/admin/": 300,  # 5 min — admin stats
        "/api/dashboard/contributor/": 300,  # 5 min — contributor stats
        "/api/dashboard/landing-stats/": 300,  # 5 min — public landing stats
        "/api/leaderboard/": 300,  # 5 min — leaderboard
        "/api/content/": 3600,  # 1 hour — static curriculum content
        "/api/challenges/today/": 300,  # 5 min — daily challenge
        "/api/recommendations/": 300,  # 5 min — recommendations
        "/api/progress/me/": 60,  # 1 min — user progress (more dynamic)
        "/api/progress/certificate/": 600,  # 10 min — certificate
        "/api/users/me/learning-path/": 300,  # 5 min — learning path
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only apply to GET requests
        if request.method != "GET":
            return response

        # Only apply to successful responses
        if response.status_code != 200:
            return response

        # Don't override existing Cache-Control headers
        if response.has_header("Cache-Control"):
            return response

        path = request.path
        for prefix, max_age in self.CACHE_RULES.items():
            if path.startswith(prefix):
                # private = only the user's browser cache, not shared CDN caches
                response["Cache-Control"] = f"private, max-age={max_age}"
                break

        return response
