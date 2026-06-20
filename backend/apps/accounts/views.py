from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import redirect
from rest_framework import generics, filters, permissions, status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
import requests as http_requests
from django.utils.text import slugify
import secrets
import os
from typing import Optional
from urllib.parse import urlencode

from django.db.models import Sum
from apps.progress.models import LessonProgress, UserBadge
from apps.progress.serializers import UserBadgeSerializer
from .serializers import (
    SignupSerializer,
    UserListSerializer,
    UserUpdateSerializer,
    EmailOrUsernameTokenObtainPairSerializer,
)
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

def unique_username_from_value(value: str) -> str:
    base = slugify(value.split("@")[0]) or "user"
    candidate = base
    suffix = 1

    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}{suffix}"
        suffix += 1

    return candidate


def frontend_url(path: str, query: Optional[dict[str, str]] = None) -> str:
    base_url = os.getenv("FRONTEND_URL") or (settings.CORS_ALLOWED_ORIGINS[0] if settings.CORS_ALLOWED_ORIGINS else "http://localhost:5173")
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url

@extend_schema(request=SignupSerializer, responses=SignupSerializer)
class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    permission_classes = [IsAuthenticated]  # check jwt authentication

    @extend_schema(responses=UserListSerializer)
    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "is_staff": request.user.is_staff,
            }
        )

    @extend_schema(request=UserUpdateSerializer, responses=UserListSerializer)
    def put(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "is_staff": request.user.is_staff,
            }
        )

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
            .order_by("-earned_at", "badge__name")
        )
        progress_points = (
            LessonProgress.objects.filter(user=request.user).aggregate(total=Sum("score"))["total"] or 0
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
    responses=OpenApiResponse(description="Returns JWT refresh & access tokens and basic user info.")
)
class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailOrUsernameTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @staticmethod
    def _unique_username_from_email(email: str) -> str:
        return unique_username_from_value(email)

    def post(self, request):
        token = request.data.get("access_token") or request.data.get("access")
        if not token:
            return Response({"detail": "No access token provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Use OAuth2 userinfo endpoint with Bearer auth for better compatibility.
            user_info_resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if not user_info_resp.ok:
                return Response({"detail": "Failed to verify Google token"}, status=status.HTTP_401_UNAUTHORIZED)

            idinfo = user_info_resp.json()
            email = idinfo.get("email")
            if not email:
                return Response({"detail": "Google account has no email"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.filter(email__iexact=email).first()
            if not user:
                username = self._unique_username_from_email(email)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=secrets.token_urlsafe(24),
                )

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

    def get(self, request):
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        if not client_id:
            return Response({"detail": "GitHub OAuth is not configured."}, status=status.HTTP_400_BAD_REQUEST)

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

    def get(self, request):
        code = request.query_params.get("code")
        if not code:
            return redirect(frontend_url("/", {"auth_error": "GitHub authorization was cancelled."}))

        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            return redirect(frontend_url("/", {"auth_error": "GitHub OAuth is not configured."}))

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
            access_token = token_response.json().get("access_token") or token_response.json().get("access")
            if not access_token:
                return redirect(frontend_url("/", {"auth_error": "GitHub did not return an access token."}))

            github_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
            user_response = http_requests.get("https://api.github.com/user", headers=github_headers, timeout=10)
            user_response.raise_for_status()
            github_user = user_response.json()

            email = github_user.get("email")
            if not email:
                email_response = http_requests.get("https://api.github.com/user/emails", headers=github_headers, timeout=10)
                email_response.raise_for_status()
                emails = email_response.json()
                primary_email = next((item for item in emails if item.get("primary") and item.get("verified")), None)
                email = primary_email.get("email") if primary_email else None

            if not email:
                return redirect(frontend_url("/", {"auth_error": "GitHub account has no verified email."}))

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
            return redirect(frontend_url("/", {"auth_error": "GitHub authentication failed."}))

@extend_schema(responses=UserListSerializer(many=True))
class UserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by("id")
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserListSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username"]
    ordering_fields = ["id", "username"]
