from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from .models import OAuthToken


class OAuth2TokenAuthentication(BaseAuthentication):
    """
    DRF Authentication Backend for validating Bearer tokens issued by the OAuth 2.0 Provider.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token_str = parts[1]
        try:
            token = OAuthToken.objects.select_related("client", "user").get(
                access_token=token_str
            )
        except OAuthToken.DoesNotExist:
            raise AuthenticationFailed("Invalid OAuth 2.0 access token.")

        if token.is_revoked:
            raise AuthenticationFailed("OAuth 2.0 access token has been revoked.")

        if token.access_token_expires_at <= timezone.now():
            raise AuthenticationFailed("OAuth 2.0 access token has expired.")

        # Attach scopes helper to token object
        setattr(token, "scopes", token.scope.split())
        return (token.user, token)

    def authenticate_header(self, request):
        return 'Bearer realm="OAuth2"'
