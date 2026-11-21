"""
ASGI config for the project.
Handles both HTTP (via Django) and WebSocket (via Django Channels).
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.opentelemetry import setup_opentelemetry

setup_opentelemetry()

django_asgi_app = get_asgi_application()

from apps.accounts.routing import websocket_urlpatterns as accounts_ws  # noqa: E402
from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.content.routing import websocket_urlpatterns as content_ws  # noqa: E402
from apps.dashboard.routing import websocket_urlpatterns as dashboard_ws  # noqa: E402
from apps.feed.routing import websocket_urlpatterns as feed_ws  # noqa: E402
from apps.monitoring.routing import websocket_urlpatterns as monitoring_ws  # noqa: E402
from apps.notifications.middleware import JWTAuthMiddleware  # noqa: E402
from apps.notifications.routing import websocket_urlpatterns as notifications_ws  # noqa
from apps.sandbox.routing import websocket_urlpatterns as sandbox_ws  # noqa: E402

combined_websocket_urlpatterns = (
    accounts_ws
    + notifications_ws
    + dashboard_ws
    + chat_ws
    + sandbox_ws
    + feed_ws
    + monitoring_ws
    + content_ws
)

from apps.chat.middleware import ProfanityFilterMiddleware
from apps.core.middleware import WebSocketRateLimitMiddleware

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            WebSocketRateLimitMiddleware(
                ProfanityFilterMiddleware(
                    JWTAuthMiddleware(URLRouter(combined_websocket_urlpatterns))
                )
            )
        ),
    }
)
