import os
from datetime import timedelta

JWT_CONFIG = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_LIFETIME", 15))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_LIFETIME", 7))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("JWT_SECRET", "your-jwt-secret-key-here"),
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# Token blacklist settings
TOKEN_BLACKLIST_ENABLED = os.getenv("TOKEN_BLACKLIST_ENABLED", "True") == "True"
TOKEN_BLACKLIST_CLEANUP_INTERVAL = timedelta(days=1)

# OAuth2 settings
OAUTH2_CONFIG = {
    "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
    "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
    "GITHUB_CLIENT_ID": os.getenv("GITHUB_CLIENT_ID"),
    "GITHUB_CLIENT_SECRET": os.getenv("GITHUB_CLIENT_SECRET"),
}
