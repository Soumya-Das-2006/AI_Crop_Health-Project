"""
Django settings for AI_Crop_Health project.

PRODUCTION-READY | CLEAN | ORGANIZED
Compatible with Django 4.2+

Generated and fixed: January 2026
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# ======================================================
# 1. BASE DIRECTORY
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================================================
# 2. LOAD ENVIRONMENT VARIABLES
# ======================================================
# Load variables from AI_Crop_Health/.env (project root)
# This MUST be done BEFORE accessing any os.getenv() calls
load_dotenv(BASE_DIR / ".env")

# ======================================================
# 3. SECURITY SETTINGS
# ======================================================

# SECRET_KEY - Required by Django
# NEVER hardcode in production - always use environment variable
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY not set in .env file. "
        "Generate one with: python manage.py shell -c "
        "\"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Allowed hosts (update for production)
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]

LOGIN_URL = "/accounts/login/"

# Production security settings (uncomment for deployment)
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_BROWSER_XSS_FILTER = True

# ======================================================
# 4. APPLICATIONS
# ======================================================
INSTALLED_APPS = [
    # Django core apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project apps
    "detection",
    "blog",
    "contact",
    "features",
    "marketplace",
    "agrolease",
    "core",
    "accounts",
]

# ======================================================
# 5. MIDDLEWARE
# ======================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RequestContextMiddleware",
]

# ======================================================
# 6. URL & WSGI CONFIGURATION
# ======================================================
ROOT_URLCONF = "AI_Crop_Health.urls"
WSGI_APPLICATION = "AI_Crop_Health.wsgi.application"

# ======================================================
# 7. TEMPLATES
# ======================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "AI_Crop_Health" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "agrolease.context_processors.admin_summary",
                "blog.context_processors.blog_sidebar",
            ],
        },
    },
]

# ======================================================
# 8. DATABASE
# ======================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Alternative: PostgreSQL (uncomment and configure)
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("DB_NAME", "ai_crop_health"),
#         "USER": os.getenv("DB_USER", "postgres"),
#         "PASSWORD": os.getenv("DB_PASSWORD", ""),
#         "HOST": os.getenv("DB_HOST", "localhost"),
#         "PORT": os.getenv("DB_PORT", "5432"),
#     }
# }

# ======================================================
# 9. PASSWORD VALIDATION
# ======================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ======================================================
# 10. INTERNATIONALIZATION
# ======================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ======================================================
# 11. STATIC FILES (CSS, JavaScript, Images)
# ======================================================
STATIC_URL = "/static/"

# Single source tree for authored static assets.
# `staticfiles/` is generated by collectstatic and is never a source directory.
STATICFILES_DIRS = [
    BASE_DIR / "AI_Crop_Health" / "static",
]

# Directory for collected static files (for production)
STATIC_ROOT = BASE_DIR / "staticfiles"

# ======================================================
# 12. MEDIA FILES (User Uploads)
# ======================================================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ======================================================
# 13. DEFAULT PRIMARY KEY FIELD TYPE
# ======================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ======================================================
# 14. API KEYS (External Services)
# ======================================================

# Google Gemini AI (for crop intelligence)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    import warnings
    warnings.warn(
        "GEMINI_API_KEY not set in .env - AI features will run in demo mode. "
        "Get your key from: https://makersuite.google.com/app/apikey",
        RuntimeWarning
    )

# OpenWeather API (for weather data)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not OPENWEATHER_API_KEY:
    import warnings
    warnings.warn(
        "OPENWEATHER_API_KEY not set in .env - Weather features may not work. "
        "Get your key from: https://openweathermap.org/api",
        RuntimeWarning
    )

# ======================================================
# 15. MACHINE LEARNING SERVICE
# ======================================================
# URL for disease detection ML service (if running separately)
ML_DETECTION_URL = os.getenv("ML_DETECTION_URL", "http://127.0.0.1:8001/api/detect")

# ======================================================
# 16. LOGGING CONFIGURATION
# ======================================================
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "features": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "detection": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / "logs").mkdir(exist_ok=True)

# ======================================================
# 17. CUSTOM SETTINGS
# ======================================================

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = False

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Cache settings (for production - use Redis)
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#     }
# }

# ======================================================
# END OF SETTINGS
# ======================================================