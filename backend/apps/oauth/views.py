import secrets
import hashlib
import base64
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from rest_framework import views, status, permissions, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import OAuthClient, OAuthAuthorizationCode, OAuthToken
from .serializers import (
    OAuthClientSerializer,
    OAuthTokenSerializer,
    AuthorizeRequestSerializer,
    TokenRequestSerializer,
    TokenIntrospectionSerializer,
    TokenRevocationSerializer,
)
from .oidc import get_jwks, generate_id_token


def _verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    if not code_challenge:
        return True
    if not code_verifier:
        return False
    if method == "S256":
        hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        calculated = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("utf-8")
        return calculated == code_challenge.rstrip("=")
    elif method == "plain":
        return code_verifier == code_challenge
    return False


class AuthorizationView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = AuthorizeRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            client = OAuthClient.objects.get(
                client_id=data["client_id"], is_active=True
            )
        except OAuthClient.DoesNotExist:
            return Response(
                {"error": "invalid_client"}, status=status.HTTP_400_BAD_REQUEST
            )

        if data["redirect_uri"] not in client.redirect_uris:
            return Response(
                {"error": "invalid_redirect_uri"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "client_id": client.client_id,
                "client_name": client.name,
                "redirect_uri": data["redirect_uri"],
                "requested_scopes": data["scope"].split(),
                "state": data.get("state", ""),
                "code_challenge": data.get("code_challenge", ""),
                "code_challenge_method": data.get("code_challenge_method", "S256"),
                "nonce": data.get("nonce", ""),
            }
        )

    def post(self, request):
        serializer = AuthorizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_action = request.data.get("action", "grant")
        state = data.get("state", "")
        redirect_uri = data["redirect_uri"]

        if user_action == "deny":
            delimiter = "&" if "?" in redirect_uri else "?"
            return Response(
                {
                    "redirect_url": f"{redirect_uri}{delimiter}error=access_denied&state={state}"
                }
            )

        try:
            client = OAuthClient.objects.get(
                client_id=data["client_id"], is_active=True
            )
        except OAuthClient.DoesNotExist:
            return Response(
                {"error": "invalid_client"}, status=status.HTTP_400_BAD_REQUEST
            )

        if redirect_uri not in client.redirect_uris:
            return Response(
                {"error": "invalid_redirect_uri"}, status=status.HTTP_400_BAD_REQUEST
            )

        code_str = f"authcode_{secrets.token_urlsafe(32)}"
        expires_at = timezone.now() + timedelta(minutes=10)

        auth_code = OAuthAuthorizationCode.objects.create(
            client=client,
            user=request.user,
            code=code_str,
            redirect_uri=redirect_uri,
            scope=data.get("scope", "openid profile email"),
            code_challenge=data.get("code_challenge", ""),
            code_challenge_method=data.get("code_challenge_method", "S256"),
            nonce=data.get("nonce", ""),
            expires_at=expires_at,
        )

        delimiter = "&" if "?" in redirect_uri else "?"
        redirect_url = f"{redirect_uri}{delimiter}code={auth_code.code}"
        if state:
            redirect_url += f"&state={state}"

        return Response(
            {
                "code": auth_code.code,
                "redirect_url": redirect_url,
            },
            status=status.HTTP_201_CREATED,
        )


class TokenView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        grant_type = data["grant_type"]

        if grant_type == "authorization_code":
            code_str = data.get("code")
            if not code_str:
                return Response(
                    {"error": "invalid_request", "error_description": "Missing code"},
                    status=400,
                )

            try:
                auth_code = OAuthAuthorizationCode.objects.select_related(
                    "client", "user"
                ).get(code=code_str)
            except OAuthAuthorizationCode.DoesNotExist:
                return Response(
                    {"error": "invalid_grant", "error_description": "Invalid code"},
                    status=400,
                )

            if not auth_code.is_valid():
                return Response(
                    {
                        "error": "invalid_grant",
                        "error_description": "Expired or used code",
                    },
                    status=400,
                )

            # Check client authentication for confidential clients
            if auth_code.client.client_type == OAuthClient.ClientType.CONFIDENTIAL:
                client_secret = data.get("client_secret")
                if not client_secret or not auth_code.client.check_client_secret(
                    client_secret
                ):
                    return Response({"error": "invalid_client"}, status=401)

            # Check PKCE
            if auth_code.code_challenge:
                code_verifier = data.get("code_verifier", "")
                if not _verify_pkce(
                    code_verifier,
                    auth_code.code_challenge,
                    auth_code.code_challenge_method,
                ):
                    return Response(
                        {
                            "error": "invalid_grant",
                            "error_description": "PKCE verification failed",
                        },
                        status=400,
                    )

            auth_code.is_used = True
            auth_code.save()

            access_token = f"at_{secrets.token_urlsafe(32)}"
            refresh_token = f"rt_{secrets.token_urlsafe(32)}"
            now = timezone.now()
            at_expires = now + timedelta(hours=1)
            rt_expires = now + timedelta(days=30)

            token_obj = OAuthToken.objects.create(
                client=auth_code.client,
                user=auth_code.user,
                access_token=access_token,
                refresh_token=refresh_token,
                scope=auth_code.scope,
                access_token_expires_at=at_expires,
                refresh_token_expires_at=rt_expires,
            )

            res_payload = {
                "access_token": token_obj.access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": token_obj.refresh_token,
                "scope": token_obj.scope,
            }

            if "openid" in auth_code.scope.split():
                issuer = getattr(settings, "OIDC_ISSUER", "http://localhost:8000")
                res_payload["id_token"] = generate_id_token(
                    user=auth_code.user,
                    client_id=auth_code.client.client_id,
                    scope=auth_code.scope,
                    nonce=auth_code.nonce,
                    issuer=issuer,
                )

            return Response(res_payload, status=200)

        elif grant_type == "client_credentials":
            client_id = data.get("client_id")
            client_secret = data.get("client_secret")
            if not client_id or not client_secret:
                return Response({"error": "invalid_client"}, status=401)

            try:
                client = OAuthClient.objects.get(client_id=client_id, is_active=True)
            except OAuthClient.DoesNotExist:
                return Response({"error": "invalid_client"}, status=401)

            if not client.check_client_secret(client_secret):
                return Response({"error": "invalid_client"}, status=401)

            scope = data.get("scope") or " ".join(client.allowed_scopes)
            access_token = f"at_cc_{secrets.token_urlsafe(32)}"
            at_expires = timezone.now() + timedelta(hours=1)

            token_obj = OAuthToken.objects.create(
                client=client,
                user=None,
                access_token=access_token,
                scope=scope,
                access_token_expires_at=at_expires,
            )

            return Response(
                {
                    "access_token": token_obj.access_token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": token_obj.scope,
                },
                status=200,
            )

        elif grant_type == "refresh_token":
            rt_str = data.get("refresh_token")
            if not rt_str:
                return Response(
                    {
                        "error": "invalid_request",
                        "error_description": "Missing refresh_token",
                    },
                    status=400,
                )

            try:
                old_token = OAuthToken.objects.select_related("client", "user").get(
                    refresh_token=rt_str
                )
            except OAuthToken.DoesNotExist:
                return Response(
                    {
                        "error": "invalid_grant",
                        "error_description": "Invalid refresh token",
                    },
                    status=400,
                )

            if not old_token.is_refresh_token_valid():
                return Response(
                    {
                        "error": "invalid_grant",
                        "error_description": "Refresh token is expired or revoked",
                    },
                    status=400,
                )

            # Refresh Token Rotation: revoke old token set
            old_token.is_revoked = True
            old_token.save(update_fields=["is_revoked"])

            # Issue new token set
            new_access_token = f"at_{secrets.token_urlsafe(32)}"
            new_refresh_token = f"rt_{secrets.token_urlsafe(32)}"
            now = timezone.now()
            at_expires = now + timedelta(hours=1)
            rt_expires = now + timedelta(days=30)

            new_token = OAuthToken.objects.create(
                client=old_token.client,
                user=old_token.user,
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                scope=old_token.scope,
                access_token_expires_at=at_expires,
                refresh_token_expires_at=rt_expires,
            )

            res_payload = {
                "access_token": new_token.access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": new_token.refresh_token,
                "scope": new_token.scope,
            }

            if old_token.user and "openid" in old_token.scope.split():
                issuer = getattr(settings, "OIDC_ISSUER", "http://localhost:8000")
                res_payload["id_token"] = generate_id_token(
                    user=old_token.user,
                    client_id=old_token.client.client_id,
                    scope=old_token.scope,
                    issuer=issuer,
                )

            return Response(res_payload, status=200)

        return Response({"error": "unsupported_grant_type"}, status=400)


class OpenIDConfigView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        issuer = getattr(settings, "OIDC_ISSUER", "http://localhost:8000")
        return Response(
            {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/oauth/authorize/",
                "token_endpoint": f"{issuer}/oauth/token/",
                "jwks_uri": f"{issuer}/.well-known/jwks.json",
                "introspection_endpoint": f"{issuer}/oauth/introspect/",
                "revocation_endpoint": f"{issuer}/oauth/revoke/",
                "response_types_supported": ["code"],
                "grant_types_supported": [
                    "authorization_code",
                    "client_credentials",
                    "refresh_token",
                ],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": [
                    "openid",
                    "profile",
                    "email",
                    "lesson:read",
                    "progress:read",
                    "progress:write",
                ],
                "token_endpoint_auth_methods_supported": [
                    "client_secret_post",
                    "client_secret_basic",
                    "none",
                ],
            }
        )


class JWKSView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(get_jwks())


class IntrospectionView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TokenIntrospectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data["token"]

        try:
            token = OAuthToken.objects.select_related("client", "user").get(
                access_token=token_str
            )
            is_valid = token.is_access_token_valid()
            return Response(
                {
                    "active": is_valid,
                    "client_id": token.client.client_id,
                    "scope": token.scope,
                    "sub": str(token.user.id) if token.user else None,
                    "username": token.user.username if token.user else None,
                    "exp": int(token.access_token_expires_at.timestamp()),
                }
            )
        except OAuthToken.DoesNotExist:
            return Response({"active": False})


class RevocationView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TokenRevocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data["token"]

        OAuthToken.objects.filter(access_token=token_str).update(is_revoked=True)
        OAuthToken.objects.filter(refresh_token=token_str).update(is_revoked=True)
        return Response({"status": "revoked"}, status=200)


class OAuthClientViewSet(viewsets.ModelViewSet):
    queryset = OAuthClient.objects.all()
    serializer_class = OAuthClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserConnectedAppsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tokens = (
            OAuthToken.objects.filter(user=request.user, is_revoked=False)
            .select_related("client")
            .order_by("-created_at")
        )
        serializer = OAuthTokenSerializer(tokens, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        OAuthToken.objects.filter(id=pk, user=request.user).update(is_revoked=True)
        return Response({"status": "revoked"}, status=200)
