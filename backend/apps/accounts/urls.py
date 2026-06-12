from django.urls import path

from .views import (
    GitHubOAuthCallbackView,
    GitHubOAuthStartView,
    GoogleLoginView,
    LoginView,
    MeView,
    RefreshView,
    SignupView,
    UserListView,
)


urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("github/", GitHubOAuthStartView.as_view(), name="github-login"),
    path("github/callback/", GitHubOAuthCallbackView.as_view(), name="github-callback"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UserListView.as_view(), name="user-list"),
]
