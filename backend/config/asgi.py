"""
ASGI config for the project.
Handles both HTTP (via Django) and WebSocket (via Django Channels).
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.dashboard.routing import websocket_urlpatterns as dashboard_ws  # noqa: E402
from apps.notifications.middleware import JWTAuthMiddleware  # noqa: E402
from apps.notifications.routing import (
    websocket_urlpatterns as notifications_ws,
)  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(notifications_ws + dashboard_ws + chat_ws))
        ),
    }
)
