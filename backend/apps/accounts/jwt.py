"""
Custom JWT signing with dynamic user-specific salt.
"""

from django.contrib.auth import get_user_model

User = get_user_model()
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import TokenError
import hashlib
import hmac


class DynamicSaltValidationError(TokenError, ValueError):
    """Exception raised when dynamic salt JWT verification fails."""

    pass


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

        # Get user from token
        user_id = self.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise DynamicSaltValidationError("User not found")

        # Check password hash matches
        stored_hash = self._get_user_password_hash(user)
        token_hash = self.get("password_hash", None)

        if token_hash is not None and not constant_time_compare(
            stored_hash, token_hash
        ):
            raise DynamicSaltValidationError(
                "Token has been invalidated (password changed)"
            )

        # Check token version matches
        stored_version = self._get_token_version(user)
        token_version = self.get("token_version", None)

        if token_version is not None and stored_version != token_version:
            raise DynamicSaltValidationError("Token has been revoked")

        # Check session_id if present
        session_id = self.get("session_id")
        if session_id:
            from .models import UserSession
            from django.utils import timezone
            from datetime import timedelta

            try:
                session = UserSession.objects.get(session_id=session_id)
                now = timezone.now()
                if now > session.last_activity + timedelta(days=7):
                    session.delete()
                    raise DynamicSaltValidationError(
                        "Session expired due to inactivity"
                    )

                # Update last_activity (debounced 5 mins)
                if now > session.last_activity + timedelta(minutes=5):
                    session.last_activity = now
                    session.save(update_fields=["last_activity"])
            except UserSession.DoesNotExist:
                raise DynamicSaltValidationError("Session has been revoked")


class DynamicSaltRefreshToken(RefreshToken):
    """
    Refresh token that uses user-specific salt.
    """

    @classmethod
    def for_user(cls, user: User):

        token = cls()
        token["user_id"] = user.pk
        token["password_hash"] = cls._get_user_password_hash(user)
        token["token_version"] = cls._get_token_version(user)
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

        # Get user from token
        user_id = self.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise DynamicSaltValidationError("User not found")

        # Check password hash matches
        stored_hash = DynamicSaltAccessToken._get_user_password_hash(user)
        token_hash = self.get("password_hash", None)

        if token_hash is not None and not constant_time_compare(
            stored_hash, token_hash
        ):
            raise DynamicSaltValidationError(
                "Refresh token has been invalidated (password changed)"
            )

        # Check token version matches
        stored_version = DynamicSaltAccessToken._get_token_version(user)
        token_version = self.get("token_version", None)

        if token_version is not None and stored_version != token_version:
            raise DynamicSaltValidationError("Refresh token has been revoked")

        # Check session_id if present
        session_id = self.get("session_id")
        if session_id:
            from .models import UserSession
            from django.utils import timezone
            from datetime import timedelta

            try:
                session = UserSession.objects.get(session_id=session_id)
                now = timezone.now()
                if now > session.last_activity + timedelta(days=7):
                    session.delete()
                    raise DynamicSaltValidationError(
                        "Session expired due to inactivity"
                    )
            except UserSession.DoesNotExist:
                raise DynamicSaltValidationError("Session has been revoked")
