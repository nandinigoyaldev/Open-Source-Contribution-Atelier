"""
ASGI config for the project.
Handles both HTTP (via Django) and WebSocket (via Django Channels).
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.telemetry import setup_telemetry

setup_telemetry()

django_asgi_app = get_asgi_application()

from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.dashboard.routing import websocket_urlpatterns as dashboard_ws  # noqa: E402
from apps.notifications.middleware import JWTAuthMiddleware  # noqa: E402
from apps.notifications.routing import (  # noqa: E402
    websocket_urlpatterns as notifications_ws,
)
from apps.sandbox.routing import websocket_urlpatterns as sandbox_ws  # noqa: E402

# Combine all WebSocket patterns across the platform modules
# Including dashboard_ws which handles real-time metric distributions
combined_websocket_urlpatterns = notifications_ws + dashboard_ws + chat_ws + sandbox_ws

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
