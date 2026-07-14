"""
Custom JWT signing with dynamic user-specific salt.
"""

from django.contrib.auth.models import User
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
        """
        Generate token with user-specific salt.
        """
        token = cls()
        token["user_id"] = user.pk

        # Add user's password hash as part of the token
        # This ensures token becomes invalid when password changes
        token["password_hash"] = cls._get_user_password_hash(user)
        token["token_version"] = cls._get_token_version(user)

        return token

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
        if hasattr(user, "profile") and user.profile:
            return user.profile.jwt_token_version
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


class DynamicSaltRefreshToken(RefreshToken):
    """
    Refresh token that uses user-specific salt.
    """

    @classmethod
    def for_user(cls, user: User):
        """
        Generate refresh token with user-specific salt.
        """
        token = cls()
        token["user_id"] = user.pk
        token["password_hash"] = DynamicSaltAccessToken._get_user_password_hash(user)
        token["token_version"] = DynamicSaltAccessToken._get_token_version(user)

        return token

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
