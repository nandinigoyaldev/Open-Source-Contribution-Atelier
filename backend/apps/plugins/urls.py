from django.urls import path, re_path
from .views import PluginListView, PluginToggleView, DynamicPluginRouterView

urlpatterns = [
    path("", PluginListView.as_view(), name="plugin-list"),
    path("<str:plugin_name>/toggle/", PluginToggleView.as_view(), name="plugin-toggle"),
    re_path(
        r"^(?P<plugin_name>[a-zA-Z0-9_-]+)/(?P<subpath>.*)$",
        DynamicPluginRouterView.as_view(),
        name="plugin-dynamic-route",
    ),
]
