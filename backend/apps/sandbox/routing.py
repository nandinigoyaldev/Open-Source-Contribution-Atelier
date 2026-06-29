from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/sandbox/$", consumers.SandboxConsumer.as_asgi()),
    re_path(r"^ws/collab/(?P<room_id>[^/]+)/?$", consumers.CollabConsumer.as_asgi()),
]
