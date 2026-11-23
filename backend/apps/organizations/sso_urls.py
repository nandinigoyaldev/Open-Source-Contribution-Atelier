from django.urls import path

from .sso_views import (
    SSOCallbackView,
    SSODiscoverView,
    SSOExchangeView,
    SSOStartView,
)

urlpatterns = [
    path("discover/", SSODiscoverView.as_view(), name="org-sso-discover"),
    path("oidc/start/", SSOStartView.as_view(), name="org-sso-start"),
    path("oidc/callback/", SSOCallbackView.as_view(), name="org-sso-callback"),
    path("exchange/", SSOExchangeView.as_view(), name="org-sso-exchange"),
]
