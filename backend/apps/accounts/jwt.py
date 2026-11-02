"""
Custom JWT signing with dynamic user-specific salt.
"""

from django.contrib.auth import get_user_model

User = get_user_model()
import hashlib
import hmac

from django.core.cache import cache
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


class DynamicSaltValidationError(TokenError, ValueError):
    """Exception raised when dynamic salt JWT verification fails."""

    pass


def _assert_claims_current(token, user, label: str) -> None:
    """Reject a token that predates the user's last password change or revocation.

    Tokens carry the first 16 characters of the password hash and the profile's token
    version. A mismatch means the password changed or every session was revoked since the
    token was issued.

    Tokens issued before those claims existed carry neither. They are not trusted blindly:
    they are only accepted if they were issued after the last password change, so they
    cannot outlive a password change either.
    """
    stored_hash = DynamicSaltAccessToken._get_user_password_hash(user)
    token_hash = token.get("password_hash", None)
    if token_hash is not None and not constant_time_compare(stored_hash, token_hash):
        raise DynamicSaltValidationError(
            f"{label} has been invalidated (password changed)"
        )

    stored_version = DynamicSaltAccessToken._get_token_version(user)
    token_version = token.get("token_version", None)
    if token_version is not None and stored_version != token_version:
        raise DynamicSaltValidationError(f"{label} has been revoked")

    if token_hash is None and token_version is None:
        profile = getattr(user, "user_profile", None)
        changed_at = getattr(profile, "last_password_change", None)
        issued_at = token.get("iat", None)
        if changed_at is not None and (
            issued_at is None or float(issued_at) < changed_at.timestamp() - 1
        ):
            raise DynamicSaltValidationError(
                f"{label} was issued before the last password change"
            )


class DynamicSaltAccessToken(AccessToken):
    """
    Access token that uses user's password hash as part of signing.
    """

    @classmethod
    def for_user(cls, user: User):

        token = cls()
        token["user_id"] = user.pk
        token["password_hash"] = cls._get_user_password_hash(user)
        token["token_version"] = cls._get_token_version(user)
        # Tenant claim used by TenantContextMiddleware to scope queries.
        token["organization_id"] = cls._get_user_organization_id(user)
        return token

    @staticmethod
    def _get_user_organization_id(user: User):
        """Return the user's default organization id, or None."""
        profile = getattr(user, "user_profile", None)
        if profile is None:
            return None
        org_id = getattr(profile, "organization_id", None)
        return int(org_id) if org_id is not None else None

    @staticmethod
    def _get_user_password_hash(user: User) -> str:
        """Get a short hash of the user's password."""
        if not user.password:
            return ""
        # Use first 16 chars of password hash as identifier
        return user.password[:16]

    @staticmethod
    def _get_token_version(user: User) -> int:
        """Get the token version from user profile."""
        if hasattr(user, "user_profile") and user.user_profile:
            return user.user_profile.jwt_token_version
        return 1

    def verify(self):
        """Verify token with dynamic salt."""
        # First perform standard verification
        super().verify()

        jti = self.get("jti")
        if jti and cache.get(f"jwt_blocklist:{jti}"):
            raise DynamicSaltValidationError("Token has been blacklisted")

        # Get user from token
        user_id = self.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise DynamicSaltValidationError("User not found")

        _assert_claims_current(self, user, "Token")

        # Check session_id if present
        session_id = self.get("session_id")
        if session_id:
            from datetime import timedelta

            from django.utils import timezone

            from .models import UserSession

            try:
                session = UserSession.objects.get(session_id=session_id)
                now = timezone.now()
                # Update last_activity (debounced 5 mins)
                if now > session.last_activity + timedelta(minutes=5):
                    session.last_activity = now
                    session.save(update_fields=["last_activity"])
            except UserSession.DoesNotExist:
                pass


class DynamicSaltRefreshToken(RefreshToken):
    """
    Refresh token that uses user-specific salt.
    """

    # Access tokens minted from this refresh token inherit its claims.
    access_token_class = DynamicSaltAccessToken

    @classmethod
    def for_user(cls, user: User):
        # Go through SimpleJWT so the token is recorded as outstanding and can be blacklisted
        # on the server (see apps.accounts.services.revoke_user_sessions).
        token = super().for_user(user)
        token["password_hash"] = DynamicSaltAccessToken._get_user_password_hash(user)
        token["token_version"] = DynamicSaltAccessToken._get_token_version(user)
        # Mirror the tenant claim on the refresh token so rotated
        # access tokens can inherit it without an extra DB hit.
        token["organization_id"] = cls._get_user_organization_id(user)
        return token

    @staticmethod
    def _get_user_organization_id(user: User):
        """Return the user's default organization id, or None."""
        profile = getattr(user, "user_profile", None)
        if profile is None:
            return None
        org_id = getattr(profile, "organization_id", None)
        return int(org_id) if org_id is not None else None

    def verify(self):
        """Verify refresh token with dynamic salt."""
        # First perform standard verification
        super().verify()

        jti = self.get("jti")
        if jti and cache.get(f"jwt_blocklist:{jti}"):
            raise DynamicSaltValidationError("Token has been blacklisted")

        # Get user from token
        user_id = self.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise DynamicSaltValidationError("User not found")

        _assert_claims_current(self, user, "Refresh token")

        # Check session_id if present
        session_id = self.get("session_id")
        if session_id:
            from datetime import timedelta

            from django.utils import timezone

            from .models import UserSession

            try:
                session = UserSession.objects.get(session_id=session_id)
                now = timezone.now()
                if now > session.last_activity + timedelta(minutes=5):
                    session.last_activity = now
                    session.save(update_fields=["last_activity"])
            except UserSession.DoesNotExist:
                pass
