import logging

logger = logging.getLogger(__name__)
import base64
import hashlib
import os
import secrets
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from django_q.tasks import async_task
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, generics, permissions, status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.progress.models import LessonProgress, UserBadge
from apps.progress.serializers import UserBadgeSerializer
from schemas.user import (
    LoginResponseSchema,
    UserCreateSchema,
    UserLoginSchema,
    UserProfileSchema,
    UserResponseSchema,
)

from .jwt import DynamicSaltRefreshToken
from .serializers import DynamicSaltTokenRefreshSerializer
from .services import notify_sessions_revoked, revoke_user_sessions


class LoginResponseSchema(UserResponseSchema):
    pass


from . import email_verification
from .models import MagicLinkToken, OTPToken, PasswordResetToken
from .serializers import (
    EmailOrUsernameTokenObtainPairSerializer,
    MagicLinkRequestSerializer,
    MagicLinkVerifySerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendVerificationSerializer,
    SignupSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from .tasks import (
    send_magic_link_email_task,
    send_otp_email_task,
    send_password_reset_email_task,
)
from .throttles import (
    EmailVerifyThrottle,
    GitHubOAuthCallbackThrottle,
    LoginThrottle,
    MagicLinkRequestThrottle,
    MagicLinkVerifyThrottle,
    OAuthThrottle,
    OtpGenerateThrottle,
    OtpVerifyThrottle,
    PasswordResetThrottle,
    ResendVerificationThrottle,
    SignupThrottle,
    StrictIdentityLoginThrottle,
    StrictIdentityMagicLinkThrottle,
    StrictIdentityPasswordResetThrottle,
    StrictIdentityResendVerificationThrottle,
    TokenRefreshThrottle,
)


def username_from_value(value: str) -> str:
    """Return a normalized username candidate from a GitHub login or email."""
    return slugify(value.split("@")[0]) or "user"


def unique_username_from_value(value: str) -> str:
    """Return a username candidate, raising when it is already in use."""
    candidate = username_from_value(value)
    if User.objects.filter(username__iexact=candidate).exists():
        raise ValueError("Username is already taken.")
    return candidate


def available_username_from_value(value: str) -> str:
    """Return an unused username derived from ``value``.

    Unlike :func:`unique_username_from_value` this never raises — social login
    must not fail just because another account already owns the preferred
    username (e.g. ``jane`` exists while ``jane@gmail.com`` signs in with
    Google). A numeric suffix is appended until the name is free.
    """
    base = (username_from_value(value) or "user")[:140]
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def frontend_url(path: str, query: Optional[dict[str, str]] = None) -> str:
    base_url = os.getenv("FRONTEND_URL") or (
        settings.CORS_ALLOWED_ORIGINS[0]
        if settings.CORS_ALLOWED_ORIGINS
        else "http://localhost:5173"
    )
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def send_verification_email(user) -> None:
    """Queue the verification link for the user's current email address."""
    key = email_verification.make_key(user)
    async_task(
        "apps.accounts.tasks.send_verification_email_task",
        user_email=user.email,
        user_username=user.username,
        verify_url=frontend_url(f"/verify-email/{key}"),
        timeout_hours=email_verification.timeout_hours(),
    )


@extend_schema(request=SignupSerializer, responses=SignupSerializer)
class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [SignupThrottle]

    def perform_create(self, serializer):
        user = serializer.save()
        # Login does not require a verified address yet, so a mail problem
        # must not turn a successful signup into an error.
        try:
            send_verification_email(user)
        except Exception:
            logger.exception(
                "Could not queue verification email for user_id=%s", user.pk
            )


@extend_schema(
    responses={
        200: OpenApiResponse(description="Email address verified."),
        400: OpenApiResponse(description="`code` is `expired_key` or `invalid_key`."),
    },
)
class VerifyEmailView(APIView):
    """
    GET /api/auth/verify-email/<key>/

    Confirm the address a verification link was sent to. Safe to call twice:
    a link that was already used answers `already_verified` rather than an
    error, so a double-click or a mail client prefetching the page does not
    show the user a failure.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [EmailVerifyThrottle]

    def get(self, request, key):
        try:
            user = email_verification.user_for_key(key)
        except email_verification.VerificationKeyExpired as exc:
            if email_verification.is_verified(exc.user):
                return Response({"status": "already_verified"})
            return Response(
                {
                    "code": "expired_key",
                    "message": "This verification link has expired. You can request a new one.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except email_verification.VerificationKeyError:
            return Response(
                {
                    "code": "invalid_key",
                    "message": "This verification link is invalid or no longer applies to this account.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email_verification.mark_verified(user):
            return Response({"status": "already_verified"})
        logger.info("Verified email address for user_id=%s", user.pk)
        return Response({"status": "verified"})


@extend_schema(
    request=ResendVerificationSerializer,
    responses=OpenApiResponse(description="Generic confirmation message."),
)
class ResendVerificationView(APIView):
    """
    POST /api/auth/resend-verification/

    Send a fresh verification link, either to an email address or to the
    owner of an expired link (`key`). The response never says whether the
    account exists or is already verified.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [
        ResendVerificationThrottle,
        StrictIdentityResendVerificationThrottle,
    ]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")  # type: ignore
        key = serializer.validated_data.get("key")  # type: ignore
        if email:
            user = User.objects.filter(email__iexact=email.strip()).first()
        else:
            user = email_verification.user_for_expired_key(key)

        if user and user.is_active and not email_verification.is_verified(user):
            try:
                send_verification_email(user)
            except Exception:
                # Same generic answer either way, so a queue failure cannot
                # reveal that the account exists.
                logger.exception(
                    "Could not queue verification email for user_id=%s", user.pk
                )

        return Response(
            {
                "message": "If that account still needs verifying, a new link is on its way."
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Get user profile",
    description="Returns current user profile information",
    responses={
        200: UserProfileSchema,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
def get_profile(request):
    pass


class MeView(APIView):
    permission_classes = [IsAuthenticated]  # check jwt authentication

    @extend_schema(responses=UserListSerializer)
    def get(self, request):
        serializer = UserListSerializer(request.user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=UserUpdateSerializer, responses=UserListSerializer)
    def put(self, request):
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance.refresh_from_db()
        if hasattr(instance, "user_profile"):
            instance.user_profile.refresh_from_db()
        response_serializer = UserListSerializer(instance, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class MyBadgesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=OpenApiResponse(
            response=UserBadgeSerializer(many=True),
            description="Returns object {progress_points: number, badges: [UserBadgeSerializer]}",
        )
    )
    def get(self, request):
        earned_badges = (
            UserBadge.objects.filter(user=request.user)
            .select_related("badge")
            .order_by("-earned_at")
        )
        progress_points = (
            LessonProgress.objects.filter(user=request.user).aggregate(
                total=Sum("score")
            )["total"]
            or 0
        )
        serializer = UserBadgeSerializer(earned_badges, many=True)

        return Response(
            {
                "progress_points": progress_points,
                "badges": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    request=EmailOrUsernameTokenObtainPairSerializer,
    responses=OpenApiResponse(
        description="Returns JWT refresh & access tokens and basic user info."
    ),
)
class UserStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=OpenApiResponse(
            description="Returns basic user stats: join date and total contributions (lessons completed)."
        )
    )
    def get(self, request):
        user = request.user

        # Count total LessonProgress entries as "contributions"
        total_contributions = LessonProgress.objects.filter(user=user).count()

        return Response(
            {
                "join_date": user.date_joined,
                "total_contributions": total_contributions,
            },
            status=status.HTTP_200_OK,
        )


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailOrUsernameTokenObtainPairSerializer
    throttle_classes = [LoginThrottle, StrictIdentityLoginThrottle]


class RefreshView(TokenRefreshView):
    serializer_class = DynamicSaltTokenRefreshSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [TokenRefreshThrottle]


class GoogleLoginError(Exception):
    """Raised while resolving a Google identity, carries an API-safe payload."""

    def __init__(
        self,
        detail: str,
        code: str = "google_login_failed",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_USERINFO_V2_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
# Tokens the frontend (and tests) use to sign in locally without Google.
GOOGLE_DEV_TOKENS = {"fake", "dev"}


class GoogleLoginView(APIView):
    """Sign in / sign up with Google.

    Accepts whichever payload the configured OAuth flow produced:

    * ``access_token`` — OAuth2 access token (implicit flow, no client secret)
    * ``id_token`` / ``credential`` — Google ID token (OpenID Connect / GIS)
    * ``code`` — OAuth2 authorization code (auth-code flow), exchanged for
      tokens server-side when ``GOOGLE_CLIENT_SECRET`` is configured

    Whichever combination arrives, the identity is verified against Google
    before a JWT is issued.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [OAuthThrottle]

    @staticmethod
    def _unique_username_from_email(email: str) -> str:
        # Kept for backward compatibility with callers: social login must never
        # fail because somebody else already owns the preferred username.
        return available_username_from_value(email)

    @staticmethod
    def _audience_matches(*candidates) -> Optional[bool]:
        """True/False when Google reported an audience, None when unknown."""
        expected = getattr(settings, "GOOGLE_CLIENT_ID", None)
        known = [c for c in candidates if isinstance(c, str) and c]
        if not expected or not known:
            return None
        return any(c == expected for c in known)

    @staticmethod
    def _reject_unverified_email(info: dict, source: str) -> None:
        if info.get("email_verified") is False and not settings.DEBUG:
            raise GoogleLoginError(
                "Your Google account email address is not verified. Verify it "
                "with Google, then try again.",
                code="google_email_unverified",
            )
        if not info.get("email"):
            raise GoogleLoginError(
                f"Google ({source}) did not return an email address for this "
                "account. Make sure the email scope is granted.",
                code="google_no_email",
            )

    def _exchange_authorization_code(
        self, code: str, redirect_uri: Optional[str]
    ) -> dict:
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
        client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)
        if not client_id or not client_secret:
            raise GoogleLoginError(
                "Google sign-in is using the authorization-code flow but "
                "GOOGLE_CLIENT_SECRET is not configured on the server. Set "
                "GOOGLE_CLIENT_SECRET in the backend environment, or set "
                "VITE_GOOGLE_OAUTH_FLOW=implicit in the frontend.",
                code="google_oauth_not_configured",
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
            )

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri

        try:
            resp = http_requests.post(GOOGLE_TOKEN_ENDPOINT, data=payload, timeout=10)
        except http_requests.RequestException as exc:
            logger.warning("Google code exchange could not reach Google: %s", exc)
            raise GoogleLoginError(
                "Could not reach Google to complete sign-in. Please try again.",
                code="google_unreachable",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        if not resp.ok:
            logger.warning(
                "Google rejected the authorization code: %s", resp.status_code
            )
            raise GoogleLoginError(
                "Google rejected the sign-in code. Please try again.",
                code="google_code_rejected",
            )

        try:
            data = resp.json()
        except ValueError:
            data = {}

        if not data.get("id_token") and not data.get("access_token"):
            raise GoogleLoginError(
                "Google did not return tokens for this sign-in. Please try again.",
                code="google_code_rejected",
            )
        return data

    def _id_token_payload(
        self, id_token: str, dev_mode: bool = False
    ) -> Optional[dict]:
        """Verify a Google ID token and return its profile payload.

        Google's tokeninfo endpoint validates the signature server-side and
        returns the token audience, so a token minted for another OAuth client
        is rejected.
        """
        try:
            resp = http_requests.get(
                f"{GOOGLE_TOKENINFO_URL}?id_token={id_token}", timeout=10
            )
            if resp.ok:
                info = resp.json()
                if self._audience_matches(info.get("aud")) is False:
                    raise GoogleLoginError(
                        "This Google sign-in token was issued for a different "
                        "OAuth client. Make sure GOOGLE_CLIENT_ID on the server "
                        "matches VITE_GOOGLE_CLIENT_ID in the frontend.",
                        code="google_audience_mismatch",
                    )
                if info.get("email"):
                    self._reject_unverified_email(info, "ID token")
                    return info
        except http_requests.RequestException as exc:
            logger.warning("Google tokeninfo request failed: %s", exc)
        except ValueError as exc:
            logger.warning("Google tokeninfo returned invalid JSON: %s", exc)

        # Fallback: treat the value as a bearer token (legacy clients send an
        # ID token in the access_token field).
        payload = self._access_token_payload(
            id_token, check_audience=False, dev_mode=dev_mode
        )
        if payload:
            return payload

        if dev_mode:
            # Local/dev credential — skip the extra network round trip.
            return None

        # Last resort: local signature verification via Google's JWKS.
        try:
            from google.auth.transport.requests import Request as GoogleAuthRequest
            from google.oauth2 import id_token as google_id_token

            info = google_id_token.verify_oauth2_token(
                id_token,
                GoogleAuthRequest(),
                audience=getattr(settings, "GOOGLE_CLIENT_ID", None) or None,
            )
            if isinstance(info, dict) and info.get("email"):
                self._reject_unverified_email(info, "ID token")
                return info
        except GoogleLoginError:
            raise
        except Exception as exc:
            logger.info("Google ID token could not be verified locally: %s", exc)
        return None

    def _access_token_payload(
        self, access_token: str, check_audience: bool = True, dev_mode: bool = False
    ) -> Optional[dict]:
        info: Optional[dict] = None
        try:
            resp = http_requests.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            if resp.ok:
                info = resp.json()
            elif not dev_mode:
                resp = http_requests.get(
                    f"{GOOGLE_USERINFO_V2_URL}?access_token={access_token}",
                    timeout=10,
                )
                if resp.ok:
                    info = resp.json()
        except (http_requests.RequestException, ValueError) as exc:
            logger.warning("Google userinfo request failed: %s", exc)

        if info is None and not dev_mode:
            # tokeninfo validates the access token and returns its audience.
            try:
                resp = http_requests.get(
                    f"{GOOGLE_TOKENINFO_URL}?access_token={access_token}", timeout=10
                )
                if resp.ok:
                    info = resp.json()
                    check_audience = True  # audience comes with this response
            except (http_requests.RequestException, ValueError) as exc:
                logger.warning("Google access-token tokeninfo failed: %s", exc)

        if not info:
            return None

        if check_audience and info.get("email"):
            try:
                resp = http_requests.get(
                    f"{GOOGLE_TOKENINFO_URL}?access_token={access_token}", timeout=10
                )
                token_info = resp.json() if resp.ok else {}
            except (http_requests.RequestException, ValueError):
                token_info = {}
            if (
                self._audience_matches(
                    token_info.get("aud"),
                    token_info.get("audience"),
                    token_info.get("azp"),
                )
                is False
            ):
                raise GoogleLoginError(
                    "This Google token was issued for a different OAuth client. "
                    "Make sure GOOGLE_CLIENT_ID on the server matches "
                    "VITE_GOOGLE_CLIENT_ID in the frontend.",
                    code="google_audience_mismatch",
                )

        self._reject_unverified_email(info, "access token")
        return info

    def _resolve_identity(self, request) -> dict:
        access_token = request.data.get("access_token") or request.data.get("access")
        id_token = request.data.get("id_token") or request.data.get("credential")
        code = request.data.get("code")
        legacy = request.data.get("token")

        if isinstance(legacy, str) and legacy:
            if legacy.count(".") == 2:
                id_token = id_token or legacy
            elif legacy.startswith("ya"):
                access_token = access_token or legacy
            else:
                code = code or legacy

        if not access_token and not id_token and not code:
            raise GoogleLoginError(
                "No access token provided",
                code="no_token",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        probe = id_token or access_token or code or ""
        # Explicit local credentials (and DEBUG builds) skip the extra Google
        # round trips once the first verification attempt comes back empty.
        dev_mode = (
            probe in GOOGLE_DEV_TOKENS
            or probe.startswith("dev-")
            or bool(settings.DEBUG)
        )

        if code:
            tokens = self._exchange_authorization_code(
                code, request.data.get("redirect_uri")
            )
            id_token = id_token or tokens.get("id_token")
            access_token = access_token or tokens.get("access_token")

        if id_token:
            payload = self._id_token_payload(id_token, dev_mode=dev_mode)
            if payload:
                return payload

        if access_token:
            payload = self._access_token_payload(
                access_token, check_audience=id_token is None, dev_mode=dev_mode
            )
            if payload:
                return payload

        if dev_mode:
            # Dev escape hatch: never allow signing in as an arbitrary email.
            # Only DEBUG builds may pick an account via the email field.
            # Dev tokens (fake / dev-*) without DEBUG always use the fixed dev email.
            requested_email = request.data.get("email")
            if settings.DEBUG and isinstance(requested_email, str) and requested_email:
                email = requested_email.strip().lower()
            else:
                email = "google_dev@example.com"
            logger.warning(
                "Google identity could not be verified; using local dev account."
            )
            return {"email": email, "email_verified": True}

        raise GoogleLoginError(
            "Failed to verify Google token", code="google_token_invalid"
        )

    def post(self, request):
        try:
            payload = self._resolve_identity(request)
        except GoogleLoginError as exc:
            return Response(
                {"detail": exc.detail, "code": exc.code}, status=exc.status_code
            )
        except Exception:
            logger.exception("Google login failed unexpectedly")
            return Response(
                {
                    "detail": "Google sign-in failed. Please try again.",
                    "code": "google_login_failed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = (payload.get("email") or "").strip().lower()
        if not email:
            return Response(
                {
                    "detail": "Google did not return an email address for this account.",
                    "code": "google_no_email",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            from django.db import IntegrityError

            try:
                user = User.objects.create_user(
                    username=available_username_from_value(email),
                    email=email,
                    password=secrets.token_urlsafe(24),
                )
            except IntegrityError:
                # Concurrent sign-in raced us to the username — reuse the row.
                user = User.objects.filter(email__iexact=email).first()
                if not user:
                    return Response(
                        {
                            "detail": "Could not create your account. Please try again.",
                            "code": "google_signup_failed",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        refresh = DynamicSaltRefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                },
            },
            status=status.HTTP_200_OK,
        )


def _github_oauth_credentials():
    """Resolve GitHub OAuth credentials at request time.

    ``settings.GITHUB_CLIENT_ID`` / ``GITHUB_CLIENT_SECRET`` are snapshotted
    from the environment when ``config.settings`` is imported. Re-check the
    environment here so OAuth keeps working when credentials are provided
    after import (container entrypoints, test runners, runtime reconfiguration).
    The dedicated ``GITHUB_OAUTH_*`` names win over the generic ``GITHUB_*``
    ones, mirroring ``config.settings``.
    """
    client_id = (
        getattr(settings, "GITHUB_OAUTH_CLIENT_ID", None)
        or getattr(settings, "GITHUB_CLIENT_ID", None)
        or os.getenv("GITHUB_OAUTH_CLIENT_ID")
        or os.getenv("GITHUB_CLIENT_ID")
    )
    client_secret = (
        getattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", None)
        or getattr(settings, "GITHUB_CLIENT_SECRET", None)
        or os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
        or os.getenv("GITHUB_CLIENT_SECRET")
    )
    return client_id, client_secret


class GitHubOAuthStartView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OAuthThrottle]

    def get(self, request):
        client_id, _client_secret = _github_oauth_credentials()
        if not client_id:
            return Response(
                {"detail": "GitHub OAuth is not configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode("ascii")).digest()
            )
            .decode("ascii")
            .rstrip("=")
        )

        request.session["github_oauth_state"] = {
            "value": state,
            "created_at": time.time(),
        }
        request.session["github_oauth_verifier"] = code_verifier

        callback_url = request.build_absolute_uri("/api/auth/github/callback/")
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return redirect(f"https://github.com/login/oauth/authorize?{params}")


class GitHubOAuthCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [GitHubOAuthCallbackThrottle]

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code:
            return redirect(
                frontend_url("/", {"auth_error": "GitHub authorization was cancelled."})
            )

        client_id, client_secret = _github_oauth_credentials()
        if not client_id or not client_secret:
            return redirect(
                frontend_url("/", {"auth_error": "GitHub OAuth is not configured."})
            )

        if not state:
            return Response(
                {"detail": "Missing state parameter."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        session_state = request.session.pop("github_oauth_state", None)
        code_verifier = request.session.pop("github_oauth_verifier", None)

        if not session_state or not code_verifier:
            return Response(
                {"detail": "OAuth session expired or invalid."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if state != session_state.get("value"):
            return Response(
                {"detail": "Invalid OAuth state."}, status=status.HTTP_401_UNAUTHORIZED
            )

        if time.time() - session_state.get("created_at", 0) > 600:
            return Response(
                {"detail": "OAuth state expired."}, status=status.HTTP_401_UNAUTHORIZED
            )

        callback_url = request.build_absolute_uri("/api/auth/github/callback/")

        from apps.core.resilience import CircuitBreaker, CircuitOpenError

        cb = CircuitBreaker("github_oauth", failure_threshold=5, recovery_timeout=30)
        try:
            with cb:
                token_response = http_requests.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": code,
                        "redirect_uri": callback_url,
                        "code_verifier": code_verifier,
                    },
                    timeout=5,
                )
                token_response.raise_for_status()
                access_token = token_response.json().get(
                    "access_token"
                ) or token_response.json().get("access")
                if not access_token:
                    return redirect(
                        frontend_url(
                            "/",
                            {"auth_error": "GitHub did not return an access token."},
                        )
                    )

                github_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                }
                user_response = http_requests.get(
                    "https://api.github.com/user", headers=github_headers, timeout=5
                )
                user_response.raise_for_status()
                github_user = user_response.json()

                email = github_user.get("email")
                if not email:
                    email_response = http_requests.get(
                        "https://api.github.com/user/emails",
                        headers=github_headers,
                        timeout=5,
                    )
                    email_response.raise_for_status()
                    emails = email_response.json()
                    primary_email = next(
                        (
                            item
                            for item in emails
                            if item.get("primary") and item.get("verified")
                        ),
                        None,
                    )
                    email = primary_email.get("email") if primary_email else None

            if not email:
                return redirect(
                    frontend_url(
                        "/", {"auth_error": "GitHub account has no verified email."}
                    )
                )

            user = User.objects.filter(email__iexact=email).first()
            username_source = github_user.get("login") or email

            # If the email-matched user already exists, use their username.
            # Otherwise derive a free username (numeric suffix if needed) so a
            # taken GitHub username never blocks social sign-up.
            if user is not None:
                github_username = user.username
            else:
                github_username = available_username_from_value(username_source)

            if not user:
                user = User.objects.create_user(
                    username=github_username,
                    email=email,
                    password=secrets.token_urlsafe(24),
                )

            refresh = DynamicSaltRefreshToken.for_user(user)
            login_code = secrets.token_urlsafe(32)
            cache.set(
                f"github-oauth-login:{login_code}",
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                timeout=60,
            )
            return redirect(
                frontend_url(
                    "/auth/github/callback",
                    {"code": login_code},
                )
            )
        except CircuitOpenError:
            return redirect(
                frontend_url(
                    "/",
                    {
                        "auth_error": "GitHub authentication service is temporarily unavailable."
                    },
                )
            )
        except Exception as e:
            logger.warning("Caught exception: %s", e)
            return redirect(
                frontend_url("/", {"auth_error": "GitHub authentication failed."})
            )


class GitHubOAuthExchangeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [GitHubOAuthCallbackThrottle]

    def post(self, request):
        code = request.data.get("code")
        if not isinstance(code, str) or not code.strip():
            return Response(
                {"detail": "Invalid authorization code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = code.strip()
        payload = cache.get(f"github-oauth-login:{code}")
        if payload is None:
            return Response(
                {"detail": "Authorization code is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache.delete(f"github-oauth-login:{code}")
        return Response(payload)


from apps.core.mixins import OrganizationScopedQuerySetMixin

from .permissions import IsAdminOrModeratorRole


@extend_schema(responses=UserListSerializer(many=True))
class UserListView(OrganizationScopedQuerySetMixin, generics.ListAPIView):
    queryset = User.objects.select_related("user_profile").order_by("id")
    permission_classes = [permissions.IsAuthenticated, IsAdminOrModeratorRole]
    serializer_class = UserListSerializer
    pagination_class = LimitOffsetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["username"]
    ordering_fields = ["id", "username"]


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Views
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses=OpenApiResponse(description="Reset email sent if account exists."),
)
class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/

    Accept an email address and send a password reset link if the account exists.
    Always returns the same response to prevent email enumeration attacks.
    Rate-limited to 3 requests/hour per IP.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetThrottle, StrictIdentityPasswordResetThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()  # type: ignore
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Invalidate any existing unused tokens for this user
            PasswordResetToken.objects.filter(user=user, is_used=False).update(
                is_used=True
            )
            reset_token = PasswordResetToken.objects.create(user=user)

            reset_url = frontend_url(
                "/reset-password", {"token": str(reset_token.token)}
            )
            timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT_MINUTES", 15)

            async_task(
                "apps.accounts.tasks.send_password_reset_email_task",
                user_email=user.email,
                user_username=user.username,
                reset_url=reset_url,
                timeout=timeout,
            )

        # Always return the same response to prevent email enumeration
        return Response(
            {
                "message": "If an account with that email exists, a password reset link has been sent."
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses=OpenApiResponse(description="Password successfully reset."),
)
class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset/confirm/

    Accept a reset token and new password to complete the password reset.
    Tokens are single-use and expire after PASSWORD_RESET_TIMEOUT_MINUTES.
    Rate-limited to 3 requests/hour per IP.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]  # type: ignore
        new_password = serializer.validated_data["new_password"]  # type: ignore

        try:
            reset_token = PasswordResetToken.objects.select_related("user").get(
                token=token_value,
                is_used=False,
            )
        except PasswordResetToken.DoesNotExist:
            return Response(
                {
                    "error": "invalid_token",
                    "message": "This reset link is invalid or has already been used.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reset_token.is_expired():
            return Response(
                {
                    "error": "expired_token",
                    "message": "This reset link has expired. Please request a new one.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = reset_token.user
        with transaction.atomic():
            user.set_password(new_password)
            user.save()
            PasswordResetToken.objects.filter(user=user, is_used=False).update(
                is_used=True
            )
            # A reset happens signed out, so every session on every device is revoked.
            revoke_user_sessions(user, notify=False)
        notify_sessions_revoked(user)

        return Response(
            {
                "message": "Your password has been successfully reset. You can now log in."
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# OTP (Email Verification) Views
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(
    request=OtpRequestSerializer,
    responses=OpenApiResponse(description="OTP sent to email if account exists."),
)
class OtpRequestView(APIView):
    """
    POST /api/auth/otp/request/

    Regenerate and send a new OTP verification code to the given email.
    Rate-limited to 3 requests/minute per IP to prevent email spam.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [OtpGenerateThrottle]

    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()  # type: ignore
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Invalidate previous unused OTP tokens
            OTPToken.objects.filter(user=user, is_used=False).update(is_used=True)
            otp_obj = OTPToken.objects.create(user=user)

            async_task(
                "apps.accounts.tasks.send_otp_email_task",
                user_email=user.email,
                user_username=user.username,
                otp_token=otp_obj.token,
            )

        return Response(
            {"message": "If the email is registered, an OTP has been sent."},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    request=OtpVerifySerializer,
    responses=OpenApiResponse(description="Email verified successfully."),
)
class OtpVerifyView(APIView):
    """
    POST /api/auth/otp/verify/

    Verify a user's email using the OTP token they received by email.
    Rate-limited to 5 requests/minute per IP to prevent OTP guessing.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [OtpVerifyThrottle]

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()  # type: ignore
        otp = serializer.validated_data["otp"]  # type: ignore

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"error": "invalid_otp"}, status=status.HTTP_400_BAD_REQUEST
            )

        token = OTPToken.objects.filter(user=user, token=otp, is_used=False).first()
        if not token:
            return Response(
                {"error": "invalid_otp"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Mark token as used
        token.is_used = True
        token.save()

        user.is_verified = True  # type: ignore[attr-defined]
        user.save(update_fields=["is_verified"])

        return Response(
            {
                "message": "Your email has been verified successfully. You can now log in."
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Magic Link Views
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(
    request=MagicLinkRequestSerializer,
    responses=OpenApiResponse(
        description="Magic link sent to email if account exists."
    ),
)
class MagicLinkRequestView(APIView):
    """
    POST /api/auth/magic-link/request/

    Accept an email address and send a magic login link if the account exists.
    Always returns the same response to prevent email enumeration attacks.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [MagicLinkRequestThrottle, StrictIdentityMagicLinkThrottle]

    def post(self, request):
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()  # type: ignore
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Invalidate any existing unused tokens for this user
            MagicLinkToken.objects.filter(user=user, is_used=False).update(is_used=True)
            magic_token = MagicLinkToken.objects.create(user=user)

            login_url = frontend_url("/magic-login", {"token": str(magic_token.token)})
            timeout = getattr(settings, "MAGIC_LINK_TIMEOUT_MINUTES", 15)

            async_task(
                "apps.accounts.tasks.send_magic_link_email_task",
                user_email=user.email,
                user_username=user.username,
                login_url=login_url,
                timeout=timeout,
            )

        return Response(
            {
                "message": "If an account with that email exists, a magic login link has been sent."
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    request=MagicLinkVerifySerializer,
    responses=OpenApiResponse(description="Logged in successfully via magic link."),
)
class MagicLinkVerifyView(APIView):
    """
    POST /api/auth/magic-link/verify/

    Accept a magic link token to log the user in.
    Tokens are single-use and expire after MAGIC_LINK_TIMEOUT_MINUTES.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [MagicLinkVerifyThrottle]

    def post(self, request):
        serializer = MagicLinkVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]  # type: ignore

        try:
            magic_token = MagicLinkToken.objects.select_related("user").get(
                token=token_value,
                is_used=False,
            )
        except MagicLinkToken.DoesNotExist:
            return Response(
                {
                    "error": "invalid_token",
                    "message": "This magic link is invalid or has already been used.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if magic_token.is_expired():
            return Response(
                {
                    "error": "expired_token",
                    "message": "This magic link has expired. Please request a new one.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = magic_token.user

        magic_token.is_used = True
        magic_token.save(update_fields=["is_used"])

        # Invalidate any existing JWTs for this user so a stolen access token
        # cannot be reused after a magic-link login.
        if hasattr(user, "user_profile"):
            user.user_profile.increment_jwt_version()

        refresh = DynamicSaltRefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                },
                "message": "You have been successfully logged in.",
            },
            status=status.HTTP_200_OK,
        )


from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


class LogoutView(APIView):
    """
    Accepts a refresh token in the request body and adds it to the blacklist.
    Requires user to be authenticated.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            import time

            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # This automatically adds the token to the BlacklistedToken model
            token = RefreshToken(refresh_token)
            token.blacklist()

            # Redis-based blacklisting of the revoked access token
            auth = request.auth
            if auth:
                access_jti = auth.get("jti")
                access_exp = auth.get("exp")
                if access_jti and access_exp:
                    access_ttl = max(0, access_exp - int(time.time()))
                    cache.set(f"jwt_blocklist:{access_jti}", True, timeout=access_ttl)

            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Logout failed unexpectedly")
            return Response(
                {"error": "Logout failed. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )


from django.http import HttpResponse, JsonResponse

from .export import DataExportService


class ExportDataView(APIView):
    """
    GET /api/users/me/export/?export_format=csv|json
    Generates a GDPR-compliant export of all personal data.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Data export file (JSON or ZIP containing CSVs)"
            ),
            400: OpenApiResponse(description="Unsupported format requested"),
        }
    )
    def get(self, request):
        export_format = request.query_params.get("export_format", "json").lower()
        service = DataExportService(request.user)

        if export_format == "json":
            json_data = service.generate_json()
            response = HttpResponse(json_data, content_type="application/json")
            response["Content-Disposition"] = (
                f'attachment; filename="data_export_{request.user.username}.json"'
            )
            return response

        elif export_format == "csv":
            zip_data = service.generate_csv_zip()
            response = HttpResponse(zip_data, content_type="application/zip")
            response["Content-Disposition"] = (
                f'attachment; filename="data_export_{request.user.username}.zip"'
            )
            return response

        return Response(
            {
                "error": "unsupported_format",
                "message": "Only 'json' and 'csv' formats are supported.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


from apps.chat.models import Message
from apps.content.models import Comment


class SecureAccountDeleteView(APIView):
    """
    DELETE /api/users/me/delete/
    Securely deletes the user's PII while anonymizing public contributions.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Account securely deleted"),
        }
    )
    def delete(self, request):
        user = request.user

        # If the user is already deleted (e.g. from a repeated request)
        if not user or not user.pk:
            return Response(status=status.HTTP_204_NO_CONTENT)

        # 1. Fetch or create Anonymous user
        anonymous_user, _ = User.objects.get_or_create(
            username="anonymous_contributor",
            defaults={
                "email": "anonymous@example.com",
                "first_name": "Anonymous",
                "last_name": "Contributor",
                "is_active": False,
            },
        )
        if anonymous_user.password == "":
            anonymous_user.set_unusable_password()
            anonymous_user.save()

        # 2. Re-assign public contributions to preserve context without PII
        Comment.objects.filter(user=user).update(user=anonymous_user)
        Message.objects.filter(user=user).update(user=anonymous_user)

        # 3. Delete the user
        # This will CASCADE and delete: UserProfile, Certificates, LessonProgress, Notes, Tokens, etc.
        user.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


import json


class LearningPathView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. Update badges dynamically
        from apps.progress.badge_evaluator import BadgeEvaluator

        BadgeEvaluator.evaluate(user)

        # 2. Load curriculum modules
        curriculum_path = Path(getattr(settings, "CURRICULUM_JSON_PATH", "")).resolve()

        if not curriculum_path.exists():
            return Response(
                {
                    "error": "Curriculum configuration file not found.",
                    "detail": f"Expected at {curriculum_path}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with open(curriculum_path, "r", encoding="utf-8") as f:
            try:
                curriculum_data = json.load(f)
            except json.JSONDecodeError as e:
                return Response(
                    {
                        "error": "Failed to parse curriculum content.",
                        "detail": str(e),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        modules = curriculum_data.get("modules", [])

        # 3. Fetch user progress, badges, and quiz attempts
        from apps.progress.models import QuizAttempt

        completed_lessons = set(
            LessonProgress.objects.filter(user=user, completed=True).values_list(
                "lesson__slug", flat=True
            )
        )

        started_lessons = set(
            LessonProgress.objects.filter(user=user).values_list(
                "lesson__slug", flat=True
            )
        )

        incorrect_questions = set(
            QuizAttempt.objects.filter(user=user, is_correct=False).values_list(
                "question_id", flat=True
            )
        )

        earned_badges = set(
            UserBadge.objects.filter(user=user).values_list("badge__slug", flat=True)
        )

        scored_modules = []
        for idx, mod in enumerate(modules):
            mod_id = mod.get("id")
            mod_title = mod.get("title")
            mod_desc = mod.get("description")
            mod_lessons = mod.get("lessons", [])

            lesson_slugs = [les.get("slug") for les in mod_lessons]

            # Determine status
            completed_count = sum(
                1 for slug in lesson_slugs if slug in completed_lessons
            )
            started_count = sum(1 for slug in lesson_slugs if slug in started_lessons)

            if len(lesson_slugs) == 0:
                status_str = "completed"
            elif completed_count == len(lesson_slugs):
                status_str = "completed"
            elif started_count > 0:
                status_str = "in progress"
            else:
                status_str = "not started"

            # Base scorer
            score = 0
            explanation = ""

            # Check incorrect quizzes for lessons in this module
            has_weak_quizzes = False
            for les_slug in lesson_slugs:
                # Quizzes have ID format: {lesson_slug}-q{quiz_idx}
                for q_id in incorrect_questions:
                    if q_id.startswith(f"{les_slug}-q"):
                        has_weak_quizzes = True
                        break
                if has_weak_quizzes:
                    break

            if status_str == "completed":
                score = 0
                explanation = "You have fully completed this module! Nice job."
            elif status_str == "in progress":
                score = 100
                explanation = "You've already started this module! Let's keep the momentum going and finish the remaining lessons."
                if has_weak_quizzes:
                    score += 30
                    explanation = "Revisit this in-progress module to improve on previous quiz mistakes and complete the lessons."
            else:  # not started
                score = 50
                explanation = "This module is next in line. Complete these lessons to learn new open source skills."
                if has_weak_quizzes:
                    score += 30
                    explanation = "Strengthen your understanding by tackling this module's lessons and quizzes."

            # Sequence order boost
            if status_str != "completed":
                score += (len(modules) - idx) * 2

            # Badge milestone connection: mod-1, mod-2, etc.
            badge_slug = f"mod-{idx + 1}"
            if status_str != "completed" and badge_slug not in earned_badges:
                score += 10

            scored_modules.append(
                {
                    "id": mod_id,
                    "title": mod_title,
                    "description": mod_desc,
                    "status": status_str,
                    "score": score,
                    "explanation": explanation,
                    "lessons_count": len(lesson_slugs),
                    "completed_lessons_count": completed_count,
                }
            )

        # If all modules are completed, recommend reviewing the first module
        all_completed = all(m["status"] == "completed" for m in scored_modules)
        if all_completed and scored_modules:
            scored_modules[0]["score"] = 1
            scored_modules[0][
                "explanation"
            ] = "You have completed the entire curriculum! Review this module to refresh your memory."

        # Find the recommended next step (highest score)
        recommended = None
        if scored_modules:
            recommended = max(scored_modules, key=lambda m: m["score"])

        return Response(
            {"modules": scored_modules, "next_step": recommended},
            status=status.HTTP_200_OK,
        )


from .serializers import (
    AvatarUploadSerializer,
    ChangePasswordSerializer,
    PasswordResetValidateTokenSerializer,
)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description="Password changed successfully.")},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"error": "Incorrect old password."}, status=status.HTTP_400_BAD_REQUEST
            )

        # The password change and the revocation succeed or fail together.
        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            PasswordResetToken.objects.filter(user=user, is_used=False).update(
                is_used=True
            )

            # The device the user is changing the password on stays signed in: keep its
            # session, revoke everything else, then issue it a fresh token pair.
            current_session = self._current_session(request, user)
            revoke_user_sessions(
                user, keep_session_id=current_session.session_id, notify=False
            )
            refresh = DynamicSaltRefreshToken.for_user(user)
            refresh["session_id"] = str(current_session.session_id)
            access = refresh.access_token
            access["session_id"] = str(current_session.session_id)
        notify_sessions_revoked(user)

        return Response(
            {
                "status": "password changed successfully",
                "access": str(access),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _current_session(request, user):
        """The device session this request belongs to, or a new one if it has none."""
        session_id = None
        auth = getattr(request, "auth", None)
        if auth is not None and hasattr(auth, "get"):
            session_id = auth.get("session_id")
        if session_id:
            session = UserSession.objects.filter(
                user=user, session_id=session_id
            ).first()
            if session is not None:
                return session
        return UserSession.objects.create(
            user=user,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        )


from rest_framework.parsers import MultiPartParser


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request=AvatarUploadSerializer,
        responses={200: OpenApiResponse(description="Avatar uploaded successfully.")},
    )
    def post(self, request):
        serializer = AvatarUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_profile = request.user.user_profile
        user_profile.avatar = serializer.validated_data["avatar"]
        user_profile.save()

        return Response(
            {
                "status": "avatar uploaded successfully",
                "avatar_url": request.build_absolute_uri(user_profile.avatar.url),
            },
            status=status.HTTP_200_OK,
        )


class ShopStreakFreezeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description="Streak freeze purchased.")}
    )
    def post(self, request):
        from apps.progress.models import StreakProfile

        streak_profile, _ = StreakProfile.objects.get_or_create(user=request.user)
        streak_profile.streak_freezes += 1
        streak_profile.save(update_fields=["streak_freezes"])
        return Response(
            {
                "status": "streak freeze purchased successfully",
                "streak_freezes": streak_profile.streak_freezes,
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetValidateTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetValidateTokenSerializer,
        responses={200: OpenApiResponse(description="Token is valid.")},
    )
    def post(self, request):
        serializer = PasswordResetValidateTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]
        try:
            reset_token = PasswordResetToken.objects.get(
                token=token_value, is_used=False
            )
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"error": "invalid_token"}, status=status.HTTP_400_BAD_REQUEST
            )

        if reset_token.is_expired():
            return Response(
                {"error": "expired_token"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"status": "password reset token is valid"}, status=status.HTTP_200_OK
        )


class UserSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserListSerializer(many=True))
    def get(self, request):
        suggestions = User.objects.exclude(id=request.user.id).order_by("-date_joined")[
            :5
        ]
        serializer = UserListSerializer(
            suggestions, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicProfileView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=UserListSerializer)
    def get(self, request, username):
        from django.shortcuts import get_object_or_404

        user = get_object_or_404(User, username=username)
        serializer = UserListSerializer(user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


from .models import UserSession
from .serializers import UserSessionSerializer


class UserSessionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSessionSerializer

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)


class UserSessionDetailView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSessionSerializer
    lookup_field = "session_id"

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)


# ─────────────────────────────────────────────────────────────────────────────
# Two-Factor Authentication (TOTP 2FA) Views
# ─────────────────────────────────────────────────────────────────────────────

from .models import TOTPDevice
from .serializers import TwoFactorDisableSerializer, TwoFactorVerifySerializer
from .totp import (
    generate_backup_codes,
    generate_totp_secret,
    get_provisioning_uri,
    verify_totp_code,
)


class TwoFactorSetupView(APIView):
    """
    POST /api/auth/2fa/setup/
    Initiate TOTP 2FA setup. Returns secret, provisioning URI, and single-use backup codes.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        device, created = TOTPDevice.objects.get_or_create(user=user)

        if not device.is_enabled:
            secret = generate_totp_secret()
            plain_backup_codes, hashed_backup_codes = generate_backup_codes()
            device.secret = secret
            device.backup_codes = hashed_backup_codes
            device.save()
        else:
            secret = device.secret
            plain_backup_codes = []

        otpauth_url = get_provisioning_uri(user.username, secret)

        return Response(
            {
                "secret": secret,
                "otpauth_url": otpauth_url,
                "backup_codes": plain_backup_codes,
                "is_enabled": device.is_enabled,
            },
            status=status.HTTP_200_OK,
        )


class TwoFactorVerifySetupView(APIView):
    """
    POST /api/auth/2fa/verify-setup/
    Verify 6-digit TOTP code to complete 2FA activation.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        device = getattr(request.user, "totp_device", None)

        if not device or not device.secret:
            return Response(
                {"error": "2FA setup has not been initiated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verify_totp_code(device.secret, code):
            return Response(
                {
                    "error": "invalid_code",
                    "message": "Invalid 2FA verification code. Please try again.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        device.is_enabled = True
        device.save(update_fields=["is_enabled"])

        return Response(
            {"status": "2FA enabled successfully", "is_enabled": True},
            status=status.HTTP_200_OK,
        )


class TwoFactorDisableView(APIView):
    """
    POST /api/auth/2fa/disable/
    Disable 2FA after password confirmation.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        password = serializer.validated_data["password"]

        if not user.check_password(password):
            return Response(
                {"error": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(user, "totp_device"):
            user.totp_device.delete()

        return Response(
            {"status": "2FA disabled successfully", "is_enabled": False},
            status=status.HTTP_200_OK,
        )


class TwoFactorStatusView(APIView):
    """
    GET /api/auth/2fa/status/
    Return 2FA status and remaining backup codes count.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        device = getattr(request.user, "totp_device", None)
        is_enabled = bool(device and device.is_enabled)
        remaining_backup_codes = (
            len(device.backup_codes) if (device and device.backup_codes) else 0
        )

        return Response(
            {
                "is_enabled": is_enabled,
                "backup_codes_remaining": remaining_backup_codes,
            },
            status=status.HTTP_200_OK,
        )


class TwoFactorGenerateBackupCodesView(APIView):
    """
    POST /api/auth/2fa/generate-backup-codes/
    Regenerate recovery backup codes (requires user password).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        password = serializer.validated_data["password"]

        if not user.check_password(password):
            return Response(
                {"error": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST
            )

        device = getattr(user, "totp_device", None)
        if not device or not device.is_enabled:
            return Response(
                {"error": "2FA is not enabled on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plain_backup_codes, hashed_backup_codes = generate_backup_codes()
        device.backup_codes = hashed_backup_codes
        device.save(update_fields=["backup_codes"])

        return Response(
            {
                "backup_codes": plain_backup_codes,
                "status": "New backup codes generated successfully",
            },
            status=status.HTTP_200_OK,
        )
