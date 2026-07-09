from django.urls import re_path

from . import consumers, webrtc_consumers

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<room_id>[^/]+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"^ws/webrtc/(?P<room_id>[^/]+)/$", webrtc_consumers.WebRTCSignalingConsumer.as_asgi()),
]
