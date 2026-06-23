import os
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "SECRET_KEY", "django-insecure-dev-key-not-for-production-use-32bytes!!"
)
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_filters",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "apps.accounts",
    "apps.content",
    "apps.progress",
    "apps.challenges",
    "apps.sandbox",
    "apps.organizations",
    "apps.webhooks",
    "rest_framework_simplejwt.token_blacklist",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.sandbox.middleware.SandboxExecutionLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,  # Prepares for PgBouncer connection pooling
        conn_health_checks=True,
    ),
    "replica": dj_database_url.config(
        env="REPLICA_DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",  # Falls back to local sqlite in dev
        conn_max_age=600,
        conn_health_checks=True,
    ),
}

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
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Email Configuration ────────────────────────────────────────────────────────
# Default: console backend (prints emails to stdout) — safe for dev/CI.
# Override EMAIL_BACKEND in production env with a real SMTP backend.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@atelier.dev")

# ── Proxy / Load-Balancer Support ─────────────────────────────────────────────
# Number of trusted proxy hops in front of Django (e.g. Nginx + AWS ALB = 2).
# Used by throttles.py to extract the real client IP from X-Forwarded-For.
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))

# ── Password Reset ─────────────────────────────────────────────────────────────
# How many minutes a password reset token remains valid.
PASSWORD_RESET_TIMEOUT_MINUTES = int(os.getenv("PASSWORD_RESET_TIMEOUT_MINUTES", "15"))

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
    },
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.accounts.exceptions.throttle_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_LIFETIME_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", "7"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# ──────────────────────────────────────────
# Django Channels + Notifications
# ──────────────────────────────────────────
INSTALLED_APPS += [
    "channels",
    "apps.notifications.apps.NotificationsConfig",
    "drf_spectacular",
    "apps.dashboard.apps.DashboardConfig",
    "apps.chat.apps.ChatConfig",
    "django.contrib.postgres",
    "apps.search.apps.SearchConfig",
]


# ──────────────────────────────────────────
# Redis Availability and Configuration (Dynamic Fallbacks)
# ──────────────────────────────────────────
import socket


def is_redis_available(url):
    try:
        if not url:
            return False
        clean_url = url.replace("redis://", "")
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
        }
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
        }
    }

# ──────────────────────────────────────────
# Celery Configuration
# ──────────────────────────────────────────
CELERY_BROKER_URL = ENV_REDIS_URL or "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"


# ──────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────
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

