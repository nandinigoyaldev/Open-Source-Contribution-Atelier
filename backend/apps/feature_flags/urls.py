from django.urls import path
from .debug_view import feature_flags_debug_view

urlpatterns = [
    path("debug/", feature_flags_debug_view, name="feature-flags-debug-api"),
]
