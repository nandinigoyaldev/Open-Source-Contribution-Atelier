from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import hashlib
import json

User = get_user_model()


class TokenService:
    @staticmethod
    def generate_tokens(user):
        """Generate access and refresh tokens"""
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": user.id,
            "username": user.username,
        }

    @staticmethod
    def refresh_access_token(refresh_token):
        """Refresh access token using refresh token"""
        try:
            token = RefreshToken(refresh_token)
            return {
                "access": str(token.access_token),
                "refresh": str(token),
            }
        except InvalidToken as e:
            return {"error": f"Invalid token: {str(e)}"}
        except TokenError as e:
            return {"error": f"Token error: {str(e)}"}

    @staticmethod
    def blacklist_token(refresh_token):
        """Blacklist a token"""
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def validate_token(token):
        """Validate a token"""
        from rest_framework_simplejwt.tokens import AccessToken

        try:
            AccessToken(token)
            return {"valid": True}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    @staticmethod
    def rotate_token(refresh_token):
        """Rotate token (invalidate old, create new)"""
        try:
            old_token = RefreshToken(refresh_token)
            user = User.objects.get(id=old_token["user_id"])

            # Blacklist old token
            old_token.blacklist()

            # Generate new tokens
            return TokenService.generate_tokens(user)
        except Exception as e:
            return {"error": str(e)}
