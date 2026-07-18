from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """
    Add the configured Content-Security-Policy header to every response.

    The middleware preserves a CSP header that may already have been set by
    a view or another middleware, allowing individual responses to provide a
    more specific policy when necessary.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        policy = getattr(
            settings,
            "CONTENT_SECURITY_POLICY",
            "",
        )

        if policy:
            response.headers.setdefault(
                "Content-Security-Policy",
                policy,
            )

        return response
