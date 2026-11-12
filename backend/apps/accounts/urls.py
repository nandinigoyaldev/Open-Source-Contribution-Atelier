from django.urls import path

from .secure_oauth import SecureGitHubOAuthCallbackView
from .views import (
    AvatarUploadView,
    ChangePasswordView,
    ExportDataView,
    GitHubOAuthExchangeView,
    GitHubOAuthStartView,
    GoogleLoginView,
    LoginView,
    LogoutView,
    MagicLinkRequestView,
    MagicLinkVerifyView,
    MeView,
    OtpRequestView,
    OtpVerifyView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetValidateTokenView,
    PublicProfileView,
    RefreshView,
    ResendVerificationView,
    AccountDeletionCancelView,
    SecureAccountDeleteView,
    ShopStreakFreezeView,
    SignupView,
    TwoFactorDisableView,
    TwoFactorGenerateBackupCodesView,
    TwoFactorSetupView,
    TwoFactorStatusView,
    TwoFactorVerifySetupView,
    UserListView,
    UserSessionDetailView,
    UserSessionListView,
    UserStatisticsView,
    UserSuggestionsView,
    VerifyEmailView,
)
from .views_webauthn import PasskeyRegisterBeginView, PasskeyRegisterFinishView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("me/delete/", SecureAccountDeleteView.as_view(), name="me-delete"),
    path("me/delete/preview/", SecureAccountDeleteView.as_view(), name="me-delete-preview"),
    path("me/delete/cancel/", AccountDeletionCancelView.as_view(), name="me-delete-cancel"),
    path("me/export/", ExportDataView.as_view(), name="me-export"),
    path("stats/", UserStatisticsView.as_view(), name="user-stats"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/suggestions/", UserSuggestionsView.as_view(), name="user-suggestions"),
    path("sessions/", UserSessionListView.as_view(), name="session-list"),
    path(
        "sessions/<uuid:session_id>/",
        UserSessionDetailView.as_view(),
        name="session-detail",
    ),
    path("profile/avatar/", AvatarUploadView.as_view(), name="avatar-upload"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path(
        "2fa/verify-setup/", TwoFactorVerifySetupView.as_view(), name="2fa-verify-setup"
    ),
    path("2fa/disable/", TwoFactorDisableView.as_view(), name="2fa-disable"),
    path("2fa/status/", TwoFactorStatusView.as_view(), name="2fa-status"),
    path(
        "2fa/generate-backup-codes/",
        TwoFactorGenerateBackupCodesView.as_view(),
        name="2fa-generate-backup-codes",
    ),
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("github/", GitHubOAuthStartView.as_view(), name="github-login"),
    path(
        "github/exchange/",
        GitHubOAuthExchangeView.as_view(),
        name="github-exchange",
    ),
    path(
        "github/callback/",
        SecureGitHubOAuthCallbackView.as_view(),
        name="github-callback",
    ),
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password-reset/validate-token/",
        PasswordResetValidateTokenView.as_view(),
        name="password-reset-validate",
    ),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("otp/request/", OtpRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OtpVerifyView.as_view(), name="otp-verify"),
    path(
        "magic-link/request/", MagicLinkRequestView.as_view(), name="magic-link-request"
    ),
    path("magic-link/verify/", MagicLinkVerifyView.as_view(), name="magic-link-verify"),
    path("verify-email/<str:key>/", VerifyEmailView.as_view(), name="verify-email"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),
    path(
        "passkey/register/begin/",
        PasskeyRegisterBeginView.as_view(),
        name="passkey-register-begin",
    ),
    path(
        "passkey/register/finish/",
        PasskeyRegisterFinishView.as_view(),
        name="passkey-register-finish",
    ),
    path("profile/<str:username>/", PublicProfileView.as_view(), name="public-profile"),
    path(
        "shop/streak-freeze/", ShopStreakFreezeView.as_view(), name="shop-streak-freeze"
    ),
]
