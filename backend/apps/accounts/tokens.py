"""
Shared JWT token generation helper.
"""

from .jwt import DynamicSaltRefreshToken


def generate_tokens_for_user(user):
    """
    Generate access and refresh JWT tokens for a given user.

    Returns:
        dict: {'access': <access_token_str>, 'refresh': <refresh_token_str>}
    """
    refresh = DynamicSaltRefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
