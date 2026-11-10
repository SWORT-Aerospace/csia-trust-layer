"""Django settings for Syncora (restaurant service dispatch).

All secrets and deployment switches come from environment variables (or a
local, uncommitted ``.env`` file). See ``.env.example`` for the full list.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines; real env vars always win."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
# The deployment's configured mode. Django's test runner flips DEBUG to False at
# runtime, so deployment checks read this instead.
DISPATCH_CONFIGURED_DEBUG = DEBUG

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.startswith("replace-me"):
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")
    # Local development only. A hosted deployment refuses to start without a real key.
    SECRET_KEY = "dev-only-insecure-key-do-not-deploy"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dispatch",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "web.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if not DEBUG:
    # Hosted: WhiteNoise serves collected static files. Locally, runserver does.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

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
                "web.context.product_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


def _database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql", "pgsql"}:
        raise ImproperlyConfigured("DATABASE_URL must be a postgres:// URL (or unset for SQLite).")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DISPATCH_SQLITE_PATH") or BASE_DIR / "db.sqlite3",
            # The web server and the timer worker are separate processes that
            # write concurrently: WAL + IMMEDIATE transactions + a busy timeout
            # make SQLite serialize writers instead of failing them.
            "OPTIONS": {
                "timeout": 20,
                "transaction_mode": "IMMEDIATE",
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            },
            # File-backed test DB so concurrency tests use real separate connections.
            "TEST": {"NAME": BASE_DIR / "test_db.sqlite3"},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "web:signin"
LOGIN_REDIRECT_URL = "web:app_home"

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DISPATCH_DEFAULT_TIME_ZONE", "America/New_York")
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --- Shared cache / rate limits --------------------------------------------
# Hosted deployments run several web processes; pairing and demo-start limits
# must be shared and atomic, so a non-debug deployment refuses to start
# without Redis. Local development falls back to an in-process counter.
DISPATCH_REDIS_URL = os.environ.get("DISPATCH_REDIS_URL", "").strip()
if DISPATCH_REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": DISPATCH_REDIS_URL,
            "KEY_PREFIX": "syncora",
            "OPTIONS": {"socket_connect_timeout": 0.5, "socket_timeout": 0.5},
        }
    }
elif not DEBUG:
    raise ImproperlyConfigured(
        "DISPATCH_REDIS_URL must point to a shared Redis when DJANGO_DEBUG is false: "
        "pairing and demo-start limits have to be shared across every web process."
    )
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Number of reverse proxies in front of the app that append to X-Forwarded-For
# (0 = trust only the socket address). Rate limits key on the client address.
DISPATCH_TRUSTED_PROXY_COUNT = int(os.environ.get("DISPATCH_TRUSTED_PROXY_COUNT", "0") or 0)
# Public endpoint limits (per client address unless noted; windows in seconds).
DISPATCH_PAIR_ATTEMPT_LIMIT = int(os.environ.get("DISPATCH_PAIR_ATTEMPT_LIMIT", "10") or 10)
DISPATCH_DEMO_PER_CLIENT_LIMIT = int(os.environ.get("DISPATCH_DEMO_PER_CLIENT_LIMIT", "30") or 30)
DISPATCH_DEMO_GLOBAL_LIMIT = int(os.environ.get("DISPATCH_DEMO_GLOBAL_LIMIT", "600") or 600)  # all clients, per hour
# Bearer token for /healthz/worker (operator monitoring). Unset = endpoint disabled.
DISPATCH_HEALTH_TOKEN = os.environ.get("DISPATCH_HEALTH_TOKEN", "")

# --- Sessions / CSRF / transport security ----------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 14  # one long shift
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True  # JS reads the token from a <meta> tag, not the cookie
X_FRAME_OPTIONS = "SAMEORIGIN"  # the demo floor view frames staff screens from the same origin
# W019 asks for DENY; SAMEORIGIN is deliberate (see above) and CSP frame-ancestors 'self' backs it.
SILENCED_SYSTEM_CHECKS = ["security.W019"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = env_bool("DISPATCH_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(os.environ.get("DISPATCH_HSTS_SECONDS", "0") or 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if not DEBUG else None

# --- Product switches --------------------------------------------------------
DISPATCH_DEMO_ENABLED = env_bool("DISPATCH_DEMO_ENABLED", True)
# Seeded demo accounts (known passwords) may sign in only when explicitly allowed.
DISPATCH_ALLOW_DEMO_LOGINS = env_bool("DISPATCH_ALLOW_DEMO_LOGINS", DEBUG)
DISPATCH_DEMO_STAFF_PASSWORD = os.environ.get("DISPATCH_DEMO_STAFF_PASSWORD", "")
DISPATCH_SETUP_OPEN = env_bool("DISPATCH_SETUP_OPEN", DEBUG)
DISPATCH_DEMO_TTL_HOURS = int(os.environ.get("DISPATCH_DEMO_TTL_HOURS", "6") or 6)
# Seconds without a worker heartbeat before staff screens warn that timers are stalled.
DISPATCH_WORKER_STALE_SECONDS = 15

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"dispatch": {"handlers": ["console"], "level": "INFO"}},
}
