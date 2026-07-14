import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url

# pyrefly: ignore [missing-import]
from django.core.exceptions import ImproperlyConfigured

from config.auth import TOKEN_BLACKLIST_ENABLED

logger = logging.getLogger(__name__)

TESTING = "test" in sys.argv or "pytest" in sys.modules

# Patch Django template context copy for Python 3.14 compatibility
import copy

from django.template.context import BaseContext


def safe_context_copy(self):
    cls = self.__class__
    new_context = cls.__new__(cls)
    for k, v in self.__dict__.items():
        if k == "dicts":
            new_context.dicts = self.dicts[:]
        else:
            setattr(new_context, k, copy.copy(v))
    return new_context


BaseContext.__copy__ = safe_context_copy

BASE_DIR = Path(__file__).resolve().parent.parent


from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.getenv(
    "SECRET_KEY", "django-insecure-dev-key-not-for-production-use-32bytes!!"
)
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable is not set")
DEBUG = os.getenv("DEBUG", "False") == "True"

# Explicit environment designation, independent of DEBUG. Used below to make
# sure DEBUG=True (and the wildcard CORS it enables) can never silently reach
# a production deployment.
DJANGO_ENV = os.getenv("DJANGO_ENV", "development")
# ──────────────────────────────────────────
# Security Headers
# ──────────────────────────────────────────

# Prevent browsers from MIME-sniffing responses away from their declared
# Content-Type.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Prevent application pages from being embedded in frames.
X_FRAME_OPTIONS = "DENY"

# Keep HSTS disabled for local development. Production defaults to one year.
SECURE_HSTS_SECONDS = int(
    os.getenv(
        "SECURE_HSTS_SECONDS",
        "0" if DEBUG else "31536000",
    )
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "True",
).lower() in {"1", "true", "yes", "on"}

# HSTS preload is opt-in because enabling it has long-lived operational impact.
SECURE_HSTS_PRELOAD = os.getenv(
    "SECURE_HSTS_PRELOAD",
    "False",
).lower() in {"1", "true", "yes", "on"}

# Restrictive default Content Security Policy.
# Allow jsDelivr because the API documentation UI loads its assets from there.
CONTENT_SECURITY_POLICY = os.getenv(
    "CONTENT_SECURITY_POLICY",
    (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob: http: https: https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "media-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
        "upgrade-insecure-requests"
    ),
)

TESTING = "test" in sys.argv or "pytest" in sys.modules

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

if not DEBUG and not TESTING and not ALLOWED_HOSTS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("ALLOWED_HOSTS cannot be empty in production.")

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Auto-include FRONTEND_URL if set and not already in the list
_frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if _frontend_url and _frontend_url not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(_frontend_url)

if not DEBUG and not TESTING and not CORS_ALLOWED_ORIGINS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS cannot be empty in production.")

CORS_ALLOW_CREDENTIALS = True
if DEBUG:
    if DJANGO_ENV == "production":
        # CORS_ALLOW_ALL_ORIGINS + CORS_ALLOW_CREDENTIALS together let any
        # website make authenticated, cookie/credential-bearing requests to
        # this API. That's fine for local development, but must never reach
        # production silently just because DEBUG was left on by mistake.
        raise ImproperlyConfigured(
            "Refusing to start: DEBUG=True while DJANGO_ENV=production. "
            "This would also silently enable CORS_ALLOW_ALL_ORIGINS together "
            "with CORS_ALLOW_CREDENTIALS, letting any website make "
            "authenticated requests to this API. Set DEBUG=False (or "
            "DJANGO_ENV to something other than 'production') to continue."
        )
    CORS_ALLOW_ALL_ORIGINS = True
# CORS_ALLOW_ALL_ORIGINS defaults to False; rely on CORS_ALLOWED_ORIGINS allowlist.

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_filters",
    "django_prometheus",
    "celery_prometheus_exporter",
    "drf_spectacular",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # ── Django-allauth ─────────────────────────────────────────────────────────
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",
    "apps.accounts",
    "apps.cache",
    "apps.core",
    "apps.localization",
    "apps.content",
    "apps.progress",
    "apps.challenges",
    "apps.accessibility",
    "apps.sandbox",
    "apps.organizations",
    "apps.billing",
    "apps.webhooks",
    "apps.notes",
    "apps.recommendations",
    "apps.rbac",
    "apps.uploads",
    "graphene_django",
    "apps.moderation",
    "apps.events",
    "apps.portfolio",
    "apps.feature_flags",
    "apps.issues",
    "apps.gamification",
    "django_q",
    "waffle",
]
# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# Rate Limit
DEFAULT_RATE = "100/hour"

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "config.logging_middleware.RequestResponseLoggingMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "config.security_middleware.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.localization.middleware.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.core.audit_middleware.AuditLogMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "waffle.middleware.WaffleMiddleware",
    "apps.cache.middleware.RateLimitMiddleware",
    "apps.sandbox.middleware.SandboxExecutionLogMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # ✅ ADDED: For email templates
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.feature_flags.context_processors.feature_flags",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(
            os.getenv("CONN_MAX_AGE", "0")
        ),  # PgBouncer uses transaction pooling, so conn_max_age=0
        conn_health_checks=True,
    ),
    "replica": dj_database_url.config(
        env="REPLICA_DATABASE_URL",
        default=os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.getenv("CONN_MAX_AGE", "0")),
        conn_health_checks=True,
    ),
}

for db_name, db_config in DATABASES.items():
    if db_config.get("ENGINE") == "django.db.backends.postgresql":
        db_config["ENGINE"] = "django_prometheus.db.backends.postgresql"
        # Disable server-side cursors to avoid issues with PgBouncer transaction pooling
        db_config.setdefault("OPTIONS", {})["DISABLE_SERVER_SIDE_CURSORS"] = True
    elif db_config.get("ENGINE") == "django.db.backends.sqlite3":
        db_config["ENGINE"] = "django_prometheus.db.backends.sqlite3"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_ROUTERS = ["config.db_router.PrimaryReplicaRouter"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Github App Configuration
GITHUB_APP = {
    "APP_ID": os.getenv("GITHUB_APP_ID"),
    "PRIVATE_KEY_PATH": os.getenv("GITHUB_PRIVATE_KEY_PATH"),
    "CLIENT_ID": os.getenv("GITHUB_CLIENT_ID"),
    "CLIENT_SECRET": os.getenv("GITHUB_CLIENT_SECRET"),
    "WEBHOOK_SECRET": os.getenv("GITHUB_WEBHOOK_SECRET"),
}
GITHUB_INSTALLATION_ID = os.getenv("GITHUB_INSTALLATION_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# ── Discord Integration ────────────────────────────────────────────────────────
# Discord webhook URL for achievement announcements
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# Whether to enable Discord announcements (can be disabled per environment)
DISCORD_ANNOUNCEMENTS_ENABLED = (
    os.getenv("DISCORD_ANNOUNCEMENTS_ENABLED", "true").lower() == "true"
)

# ── Email Configuration ────────────────────────────────────────────────────────
# Default: console backend (prints emails to stdout) — safe for dev/CI.
# Override EMAIL_BACKEND in production env with a real SMTP backend.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@atelier.dev")

# ── Frontend URL for password reset links ────────────────────────────────────
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
SITE_NAME = os.getenv("SITE_NAME", "Open Source Contribution Atelier")

# ── Proxy / Load-Balancer Support ─────────────────────────────────────────────
# Number of trusted proxy hops in front of Django (e.g. Nginx + AWS ALB = 2).
# Used by throttles.py to extract the real client IP from X-Forwarded-For.
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))

# ── Password Reset ─────────────────────────────────────────────────────────────
# How many minutes a password reset token remains valid.
PASSWORD_RESET_TIMEOUT_MINUTES = int(os.getenv("PASSWORD_RESET_TIMEOUT_MINUTES", "15"))

# ── OTP Email Verification ───────────────────────────────────────────────────
# How many minutes an OTP verification code remains valid.
OTP_TIMEOUT_MINUTES = int(os.getenv("OTP_TIMEOUT_MINUTES", "10"))

REST_FRAMEWORK = {
    # ── Default Throttle Classes ─────────────────────────────────────────────
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # ── Throttle Rates ───────────────────────────────────────────────────────
    # Sandbox endpoints
    # Auth endpoints (brute-force + spam protection)
    "DEFAULT_THROTTLE_RATES": {
        # ── Global Default ───────────────────────────────────────────────────
        "anon": "100/minute",
        "user": "1000/minute",
        # ── Sandbox ──────────────────────────────────────────────────────────
        "sandbox_anon": "10/minute",
        "sandbox_user": "10/minute",
        "help_request": "5/hour",
        # ── Authentication ───────────────────────────────────────────────────
        "auth_login": os.getenv("RATE_AUTH_LOGIN", "5/minute"),
        "auth_signup": os.getenv("RATE_AUTH_SIGNUP", "10/hour"),
        "auth_token_refresh": os.getenv("RATE_AUTH_TOKEN_REFRESH", "30/minute"),
        "auth_otp_generate": os.getenv("RATE_AUTH_OTP_GENERATE", "3/minute"),
        "auth_otp_verify": os.getenv("RATE_AUTH_OTP_VERIFY", "5/minute"),
        "auth_password_reset": os.getenv("RATE_AUTH_PASSWORD_RESET", "3/hour"),
        "auth_oauth": os.getenv("RATE_AUTH_OAUTH", "20/minute"),
        "auth_magic_link_request": os.getenv(
            "RATE_AUTH_MAGIC_LINK_REQUEST", "3/minute"
        ),
        "auth_magic_link_verify": os.getenv("RATE_AUTH_MAGIC_LINK_VERIFY", "5/minute"),
        # ── Chat ─────────────────────────────────────────────────────────────
        "chat_message": "30/minute",
    },
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_SCHEMA_CLASS": "config.openapi.ThrottleAutoSchema",
    "EXCEPTION_HANDLER": "apps.accounts.exceptions.throttle_exception_handler",
}

# ============================================================
# ✅ UPDATED: SimpleJWT Configuration with Dynamic Salt
# ============================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_LIFETIME_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", "7"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # ✅ Custom token classes for dynamic salt
    "ACCESS_TOKEN_CLASS": ("apps.accounts.jwt.DynamicSaltAccessToken",),
    "REFRESH_TOKEN_CLASS": ("apps.accounts.jwt.DynamicSaltRefreshToken",),
    # ✅ Other JWT settings
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("apps.accounts.jwt.DynamicSaltAccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=30),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# ──────────────────────────────────────────
# Django-allauth Configuration
# ──────────────────────────────────────────
SITE_ID = 1

SOCIALACCOUNT_PROVIDERS = {
    "github": {
        "APP": {
            "client_id": os.getenv("GITHUB_OAUTH_CLIENT_ID"),
            "secret": os.getenv("GITHUB_OAUTH_CLIENT_SECRET"),
        },
        "SCOPE": [
            "user",
            "repo",
            "read:user",
        ],
    },
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        },
        "SCOPE": [
            "profile",
            "email",
        ],
    },
}

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_ADAPTER = "apps.accounts.allauth_adapter.CustomSocialAccountAdapter"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True


# ──────────────────────────────────────────
# Django Channels + Notifications
# ──────────────────────────────────────────
INSTALLED_APPS += [
    "channels",
    "apps.notifications.apps.NotificationsConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.chat.apps.ChatConfig",
    "django.contrib.postgres",
    "apps.search.apps.SearchConfig",
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
] or [
    "http://localhost:8000",
    "http://localhost:5173",
]

# Auto-include FRONTEND_URL if set and not already in the list
if _frontend_url and _frontend_url not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(_frontend_url)

# ──────────────────────────────────────────
# Redis Availability and Configuration (Dynamic Fallbacks)
# ──────────────────────────────────────────
import socket


def is_redis_available(url):
    try:
        if not url:
            return False
        clean_url = url.replace("rediss://", "").replace("redis://", "")
        host_port = clean_url.split("/")[0]
        if "@" in host_port:
            host_port = host_port.split("@")[1]
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 6379

        # Test connection with a very short timeout
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


# Candidates check: use REDIS_URL if set, or default to standard local redis host for check
ENV_REDIS_URL = os.getenv("REDIS_URL", "")
CHECK_REDIS_URL = ENV_REDIS_URL or "redis://127.0.0.1:6379"

if is_redis_available(CHECK_REDIS_URL):
    REDIS_URL = CHECK_REDIS_URL
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "capacity": 1500,
                "expiry": 10,
            },
        },
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        },
        "l1_memory": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "atelier-l1-cache",
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "atelier-unique-cache",
        },
        "l1_memory": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "atelier-l1-cache",
        },
    }

# Cache timeout for Search API (in seconds) - Default: 1 hour
SEARCH_CACHE_TIMEOUT = 60 * 60

# ──────────────────────────────────────────
# Django-Q Configuration
# ──────────────────────────────────────────
# Use Redis as the broker when available; fall back to the ORM (SQLite/Postgres)
# so that local dev and CI work without a running Redis instance.
_q_broker: dict = (
    {"redis": ENV_REDIS_URL}
    if is_redis_available(CHECK_REDIS_URL) and ENV_REDIS_URL
    else {"orm": "default"}
)
Q_CLUSTER = {
    "name": "atelier",
    "workers": 4,
    "timeout": 90,
    "retry": 120,
    "queue_limit": 50,
    "bulk": 10,
    **_q_broker,
}
# Audit Logging
AUDIT_LOG_ENABLED = True

# Configure audit logger
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(message)s',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'audit.log',
            'formatter': 'json',
        },
    },
    'loggers': {
        'audit': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ──────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────
REQUEST_LOGGING_VERBOSITY = os.getenv("REQUEST_LOGGING_VERBOSITY", "minimal")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "mask_sensitive_data": {
            "()": "config.logging_filters.SensitiveDataFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["mask_sensitive_data"],
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


GRAPHENE = {"SCHEMA": "config.schema.schema"}

GRAPHENE = {"SCHEMA": "config.schema.schema"}

# ──────────────────────────────────────────
# Curriculum JSON Path
# ──────────────────────────────────────────
# Path to the curriculum.json file used for module definitions and learning paths.
# Default resolves to frontend/public/content/curriculum.json relative to project root.
# Override with CURRICULUM_JSON_PATH env var for Docker/production deployments.
CURRICULUM_JSON_PATH = os.getenv(
    "CURRICULUM_JSON_PATH",
    str(
        (
            BASE_DIR / ".." / "frontend" / "public" / "content" / "curriculum.json"
        ).resolve()
    ),
)

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_STORE_EAGER_RESULT = True

# Waffle Feature Flags
WAFFLE_CREATE_MISSING_FLAGS = True
WAFFLE_FLAG_DEFAULT = False

# Files are assembled outside MEDIA_ROOT and remain inaccessible until clean.
UPLOAD_QUARANTINE_ROOT = Path(os.getenv("UPLOAD_QUARANTINE_ROOT", BASE_DIR / "quarantine"))
UPLOAD_MAX_SIZES = {
    "avatar": int(os.getenv("UPLOAD_AVATAR_MAX_BYTES", str(5 * 1024 * 1024))),
    "project": int(os.getenv("UPLOAD_PROJECT_MAX_BYTES", str(50 * 1024 * 1024))),
    "lesson": int(os.getenv("UPLOAD_LESSON_MAX_BYTES", str(50 * 1024 * 1024))),
}
UPLOAD_ALLOWED_TYPES = ("jpeg", "png", "webp", "gif", "svg", "pdf", "markdown", "text", "zip", "gzip")
UPLOAD_AVATAR_ALLOWED_TYPES = ("jpeg", "png", "webp", "gif", "svg")

CLAMAV_HOST = os.getenv("CLAMAV_HOST", "127.0.0.1")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
CLAMAV_SOCKET = os.getenv("CLAMAV_SOCKET", "")
UPLOAD_SCAN_FAIL_CLOSED = os.getenv("UPLOAD_SCAN_FAIL_CLOSED", "true").lower() == "true"
