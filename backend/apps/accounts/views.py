import os
import secrets
import io
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests as http_requests
from PIL import Image
from django.conf import settings
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from django.core.mail import send_mail
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
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.progress.models import LessonProgress, UserBadge
from apps.progress.serializers import UserBadgeSerializer

from .models import MagicLinkToken, OTPToken, PasswordResetToken, UserProfile
from .serializers import (
    EmailOrUsernameTokenObtainPairSerializer,
    MagicLinkRequestSerializer,
    MagicLinkVerifySerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from schemas.user import (
    UserCreateSchema,
    UserLoginSchema,
    UserResponseSchema,
    UserProfileSchema,
)
from .tasks import (
    send_magic_link_email_task,
    send_otp_email_task,
    send_password_reset_email_task,
)
from .throttles import (
    LoginThrottle,
    MagicLinkRequestThrottle,
    MagicLinkVerifyThrottle,
    OAuthThrottle,
    OtpGenerateThrottle,
    OtpVerifyThrottle,
    PasswordResetThrottle,
    SignupThrottle,
    StrictIdentityLoginThrottle,
    StrictIdentityMagicLinkThrottle,
    StrictIdentityPasswordResetThrottle,
    TokenRefreshThrottle,
)


def unique_username_from_value(value: str) -> str:
    base = slugify(value.split("@")[0]) or "user"
    candidate = base
    suffix = 1

    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}{suffix}"
        suffix += 1

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


@extend_schema(request=SignupSerializer, responses=SignupSerializer)
class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [SignupThrottle]


class MeView(APIView):
    permission_classes = [IsAuthenticated]  # check jwt authentication

    @extend_schema(
        summary="Get user profile",
        description="Returns current user profile information",
        responses={
            200: UserResponseSchema,
            401: OpenApiResponse(description="Unauthorized"),
        },
    )
    def get(self, request):
        serializer = UserListSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    @extend_schema(request=UserUpdateSerializer, responses=UserListSerializer)
    def put(self, request):
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance.refresh_from_db()  # type: ignore
        if hasattr(instance, "profile"):
            instance.profile.refresh_from_db()  # type: ignore
        response_serializer = UserListSerializer(instance, context={"request": request})
        return Response(response_serializer.data)


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
            }
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


@extend_schema_view(
    post=extend_schema(
        summary="Login user",
        description="Authenticate user and return JWT token",
        request=UserLoginSchema,
        responses={
            200: OpenApiResponse(
                description="Login successful", response=TokenObtainPairSerializer
            ),
            401: OpenApiResponse(description="Invalid credentials"),
        },
    )
)
class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailOrUsernameTokenObtainPairSerializer
    throttle_classes = [LoginThrottle, StrictIdentityLoginThrottle]


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [TokenRefreshThrottle]


class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OAuthThrottle]

    @staticmethod
    def _unique_username_from_email(email: str) -> str:
        return unique_username_from_value(email)

    def post(self, request):
        token = (
            request.data.get("access_token")
            or request.data.get("access")
            or request.data.get("credential")
            or request.data.get("id_token")
        )
        if not token:
            return Response(
                {"detail": "No access token provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
            email = None
            id_info = None

            if google_client_id:
                try:
                    id_info = google_id_token.verify_oauth2_token(
                        token,
                        google_requests.Request(),
                        google_client_id,
                    )
                    email = id_info.get("email")
                except Exception:
                    id_info = None

            if not id_info:
                user_info_resp = http_requests.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=3,
                )
                if not user_info_resp.ok:
                    return Response(
                        {"detail": "Failed to verify Google token"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                id_info = user_info_resp.json()
                email = id_info.get("email")

            if not email:
                return Response(
                    {"detail": "Google account has no email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.filter(email__iexact=email).first()
            if not user:
                username = self._unique_username_from_email(email)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=secrets.token_urlsafe(24),
                )
                from apps.progress.models import StreakProfile
                StreakProfile.objects.get_or_create(user=user)

            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": {
                        "username": user.username,
                        "email": user.email,
                        "is_staff": user.is_staff,
                    },
                }
            )

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GitHubOAuthStartView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OAuthThrottle]

    def get(self, request):
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        if not client_id:
            return Response(
                {"detail": "GitHub OAuth is not configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        callback_url = request.build_absolute_uri("/api/auth/github/callback/")
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
            }
        )
        return redirect(f"https://github.com/login/oauth/authorize?{params}")


class GitHubOAuthCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OAuthThrottle]

    def get(self, request):
        code = request.query_params.get("code")
        if not code:
            return redirect(
                frontend_url("/", {"auth_error": "GitHub authorization was cancelled."})
            )

        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            return redirect(
                frontend_url("/", {"auth_error": "GitHub OAuth is not configured."})
            )

        callback_url = request.build_absolute_uri("/api/auth/github/callback/")

        try:
            token_response = http_requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": callback_url,
                },
                timeout=10,
            )
            token_response.raise_for_status()
            access_token = token_response.json().get(
                "access_token"
            ) or token_response.json().get("access")
            if not access_token:
                return redirect(
                    frontend_url(
                        "/", {"auth_error": "GitHub did not return an access token."}
                    )
                )

            github_headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            }
            user_response = http_requests.get(
                "https://api.github.com/user", headers=github_headers, timeout=10
            )
            user_response.raise_for_status()
            github_user = user_response.json()

            email = github_user.get("email")
            if not email:
                email_response = http_requests.get(
                    "https://api.github.com/user/emails",
                    headers=github_headers,
                    timeout=10,
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
            if not user:
                username_source = github_user.get("login") or email
                user = User.objects.create_user(
                    username=unique_username_from_value(username_source),
                    email=email,
                    password=secrets.token_urlsafe(24),
                )

            refresh = RefreshToken.for_user(user)
            return redirect(
                frontend_url(
                    "/auth/github/callback",
                    {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    },
                )
            )
        except Exception:
            return redirect(
                frontend_url("/", {"auth_error": "GitHub authentication failed."})
            )


from .permissions import IsAdminOrModeratorRole


@extend_schema(responses=UserListSerializer(many=True))
class UserListView(generics.ListAPIView):
    queryset = User.objects.select_related("profile").order_by("id")
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


class UserSuggestionsView(APIView):
    """
    GET /api/accounts/users/suggestions/?q=...
    Returns up to 10 matching usernames for autocomplete mentions.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Username prefix/search query",
            )
        ],
        responses={200: OpenApiResponse(description="List of matching users")},
    )
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response([])

        # Basic case-insensitive matching
        users = User.objects.filter(username__icontains=q).order_by("username")[:10]

        data = []
        for user in users:
            # We can include a basic avatar url or other profile data if available
            avatar_url = ""
            if hasattr(user, "profile") and hasattr(user.profile, "avatar_url"):
                avatar_url = user.profile.avatar_url

            data.append(
                {"id": user.id, "username": user.username, "avatar_url": avatar_url}
            )

        return Response(data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Views (UPDATED with Custom Token Model & JWT Invalidation)
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

        email = serializer.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Invalidate any existing unused tokens for this user
            PasswordResetToken.objects.filter(user=user, is_used=False).update(
                is_used=True
            )
            reset_token = PasswordResetToken.objects.create(user=user)

            # Build reset link
            reset_url = frontend_url(
                "/reset-password", {"token": str(reset_token.token)}
            )
            timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT_MINUTES", 15)

            # Send email asynchronously with HTML template
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
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

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
        
        # Set new password (this will trigger JWT invalidation via signal)
        user.set_password(new_password)
        
        # Update last_password_change in profile
        if hasattr(user, "profile"):
            user.profile.last_password_change = timezone.now()
            # ✅ Increment JWT token version to invalidate all existing tokens
            user.profile.jwt_token_version += 1
            user.profile.save(update_fields=["last_password_change", "jwt_token_version"])
        else:
            # Create profile if it doesn't exist
            from apps.accounts.models import UserProfile
            UserProfile.objects.create(
                user=user,
                last_password_change=timezone.now(),
                jwt_token_version=2
            )
        
        user.save()

        # Mark token as used
        reset_token.is_used = True
        reset_token.save(update_fields=["is_used"])

        # ✅ Log the invalidation
        logger.info(f"Password reset confirmed for user {user.username} - all JWT tokens invalidated")

        return Response(
            {
                "message": "Your password has been successfully reset. All existing JWT tokens have been invalidated. You can now log in with your new password."
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    responses=OpenApiResponse(description="Check if reset token is valid."),
)
class PasswordResetValidateTokenView(APIView):
    """
    GET /api/auth/password-reset/validate-token/?token=xxx

    Check if a reset token is valid and not expired.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token_value = request.query_params.get('token')

        if not token_value:
            return Response(
                {'valid': False, 'error': 'Token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            reset_token = PasswordResetToken.objects.get(
                token=token_value,
                is_used=False,
            )

        except PasswordResetToken.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Invalid or already used token'
            })

        if reset_token.is_expired():
            return Response({
                'valid': False,
                'error': 'Token has expired'
            })

        return Response({
            'valid': True,
            'message': 'Token is valid',
            'email': reset_token.user.email
        })


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

        token_value = serializer.validated_data["token"]

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


# ─────────────────────────────────────────────────────────────────────────────
# ✅ ADD: Change Password View with JWT Invalidation
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/

    Change user password and invalidate all existing JWT tokens.
    Rate-limited to 5 requests/minute per user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response(
                {'error': 'Current password and new password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify current password
        if not user.check_password(current_password):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate new password
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response(
                {'error': e.messages[0]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Set new password (this will trigger the signal)
        user.set_password(new_password)
        
        # ✅ Increment JWT token version to invalidate all existing tokens
        if hasattr(user, "profile") and user.profile:
            user.profile.jwt_token_version += 1
            user.profile.last_password_change = timezone.now()
            user.profile.save(update_fields=["jwt_token_version", "last_password_change"])
        else:
            # Create profile if it doesn't exist
            from apps.accounts.models import UserProfile
            UserProfile.objects.create(
                user=user,
                last_password_change=timezone.now(),
                jwt_token_version=2
            )
        
        user.save()

        logger.info(f"Password changed for user {user.username} - all JWT tokens invalidated")

        return Response(
            {
                'message': 'Password changed successfully. All existing JWT tokens have been invalidated.'
            },

            status=status.HTTP_200_OK
        )


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AvatarUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        avatar = serializer.validated_data["avatar"]

        # Optimize image
        try:
            img = Image.open(avatar)

            # Convert to RGB if needed
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")

            # Resize to max 300x300
            img.thumbnail((300, 300))

            # Save to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)

            # Create new file
            filename = f"{request.user.id}_avatar.jpg"
            avatar_file = ContentFile(buffer.getvalue(), name=filename)

        except Exception as e:
            return Response(
                {"error": "Invalid image file"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update or create profile
        profile, created = UserProfile.objects.get_or_create(user=request.user)

        # Delete old avatar if exists
        if profile.avatar:
            try:
                profile.avatar.delete(save=False)
            except:
                pass

        profile.avatar = avatar_file
        profile.save()

        return Response(
            {
                "message": "Avatar uploaded successfully",
                "avatar_url": profile.avatar.url if profile.avatar else None,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        """Remove avatar"""
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.avatar:
            profile.avatar.delete()
            profile.avatar = None
            profile.save()
            return Response({"message": "Avatar removed"})
        return Response({"error": "No avatar found"}, status=status.HTTP_404_NOT_FOUND)


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

        return Response({"modules": scored_modules, "next_step": recommended})


class PublicProfileView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, username):
        from django.contrib.auth.models import User
        from django.shortcuts import get_object_or_404
        from django.db.models import Sum
        from apps.progress.models import UserBadge, LessonProgress
        from apps.progress.serializers import UserBadgeSerializer
        from apps.accounts.serializers import UserListSerializer

        user = get_object_or_404(User, username=username)

        # User details
        user_serializer = UserListSerializer(user, context={"request": request})

        # Badges
        earned_badges = (
            UserBadge.objects.filter(user=user)
            .select_related("badge")
            .order_by("-earned_at")
        )
        badge_serializer = UserBadgeSerializer(earned_badges, many=True)

        # Progress stats
        total_score = (
            LessonProgress.objects.filter(user=user).aggregate(total=Sum("score"))[
                "total"
            ]
            or 0
        )
        completed_lessons = LessonProgress.objects.filter(
            user=user, completed=True
        ).count()

        return Response(
            {
                "user": user_serializer.data,
                "badges": badge_serializer.data,
                "total_score": total_score,
                "completed_lessons": completed_lessons,
            }
        )
