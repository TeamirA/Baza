"""
Django settings for config project.

All environment-specific values are read from environment variables.
Locally they come from `.env` (see `.env.example`) and optionally
`.env.local` (from `vercel env pull`); on Vercel they come from the
project's Environment Variables. Values already in the environment win.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local")  # from `vercel env pull .env.local`


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core ---------------------------------------------------------------

DEBUG = env_bool("DEBUG", False)

# In production SECRET_KEY must come from the environment. If it's missing we leave
# it empty rather than raising here: build steps like collectstatic and migrate
# don't need it, and Django itself refuses to serve requests with an empty key.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY and DEBUG:
    SECRET_KEY = "django-insecure-local-dev-only-key"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost,.vercel.app")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app")


# --- Applications -------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_components",
    "products",
    "orders",
    "users",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.LegacyHostRedirectMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "orders.context_processors.cart",
                "products.context_processors.wishlist",
                "users.context_processors.features",
            ],
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
                "django_components.template_loader.Loader",
            ],
            "builtins": ["django_components.templatetags.component_tags", "products.templatetags.money"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Database -----------------------------------------------------------
# DATABASE_URL (Postgres via the Vercel/Neon integration) wins; otherwise SQLite.
# Neon's DATABASE_URL goes through a transaction-mode pooler, so keep connections
# short-lived and avoid server-side cursors.

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "0")),
        conn_health_checks=True,
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True


# --- Auth ---------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Shown in the header, page titles and emails.
STORE_NAME = os.environ.get("STORE_NAME", "Baza")

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "products:list"
LOGOUT_REDIRECT_URL = "products:list"


# --- I18N ---------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Static files -------------------------------------------------------
# On Vercel, collectstatic runs automatically during the build and STATIC_ROOT is
# served from the CDN. WhiteNoise serves files for local production-mode runs.

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "django_components.finders.ComponentsFileSystemFinder",
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Uploaded media (product photos) -------------------------------------
# Production: Vercel Blob (set automatically when the Blob store is connected to
# the project). Locally, without a token: MEDIA_ROOT, served by Django in DEBUG.
BLOB_READ_WRITE_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Vercel Functions reject request bodies over 4.5 MB, so cap uploads below that.
MAX_IMAGE_UPLOAD_BYTES = 4 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Production hardening ----------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# --- Email ---------------------------------------------------------------
# Any SMTP provider works (Resend, Postmark, SendGrid, Gmail...). Without
# EMAIL_HOST, emails print to the console in development and are skipped in
# production, and the "Forgot password?" link is hidden.

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_ENABLED = bool(EMAIL_HOST)
if EMAIL_ENABLED:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_TIMEOUT = 10
elif DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"{STORE_NAME} <no-reply@example.com>")

# Public address of the site, used for links in emails sent outside a request
# (e.g. from the Stripe webhook). Example: https://baza-market.vercel.app
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
# Old addresses whose page views redirect to SITE_URL (the store was first
# deployed as corner-store-omega.vercel.app).
LEGACY_HOSTS = env_list("LEGACY_HOSTS", "corner-store-omega.vercel.app")


# --- Orders -------------------------------------------------------------

# Unpaid orders hold their stock this long, then the daily cron cancels them.
ORDER_HOLD_HOURS = int(os.environ.get("ORDER_HOLD_HOURS", "24"))

# Vercel Cron sends "Authorization: Bearer <CRON_SECRET>"; the cron endpoint
# refuses requests without it. Set it in the Vercel project's env vars.
CRON_SECRET = os.environ.get("CRON_SECRET", "")


# --- Error monitoring ---------------------------------------------------

from config.sentry import init_sentry  # noqa: E402

init_sentry(os.environ)


# --- Stripe (used from Phase 3) ----------------------------------------

STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


# --- django-components --------------------------------------------------
# Global widgets live in <BASE_DIR>/components/, app widgets in <app>/components/.

COMPONENTS = {
    "dirs": [BASE_DIR / "components"],
    "app_dirs": ["components"],
    "reload_on_file_change": DEBUG,
}
