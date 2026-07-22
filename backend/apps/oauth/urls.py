from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthorizationView,
    TokenView,
    OpenIDConfigView,
    JWKSView,
    IntrospectionView,
    RevocationView,
    OAuthClientViewSet,
    UserConnectedAppsViewSet,
)

app_name = "oauth"

router = DefaultRouter()
router.register("clients", OAuthClientViewSet, basename="oauth-client")
router.register("user-apps", UserConnectedAppsViewSet, basename="user-connected-app")

urlpatterns = [
    path("oauth/authorize/", AuthorizationView.as_view(), name="authorize"),
    path("oauth/token/", TokenView.as_view(), name="token"),
    path("oauth/introspect/", IntrospectionView.as_view(), name="introspect"),
    path("oauth/revoke/", RevocationView.as_view(), name="revoke"),
    path(
        ".well-known/openid-configuration",
        OpenIDConfigView.as_view(),
        name="openid-config",
    ),
    path(".well-known/jwks.json", JWKSView.as_view(), name="jwks"),
    path("api/oauth/", include(router.urls)),
]
