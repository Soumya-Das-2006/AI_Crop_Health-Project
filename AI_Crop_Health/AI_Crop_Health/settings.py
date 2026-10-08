"""
Django settings for AI_Crop_Health project.

PRODUCTION-READY | CLEAN | ORGANIZED
Compatible with Django 4.2+

Generated and fixed: January 2026
"""

from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
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

def _env_list(name, default=''):
    """Read a comma-separated environment variable into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(
        os.getenv('DJANGO_SECURE_HSTS_SECONDS', '31536000')
    )
    SECURE_HSTS_INCLUDE_SUBDOMAINS = (
        os.getenv('DJANGO_HSTS_INCLUDE_SUBDOMAINS', 'False').strip().lower() == 'true'
    )
    SECURE_HSTS_PRELOAD = (
        os.getenv('DJANGO_HSTS_PRELOAD', 'False').strip().lower() == 'true'
    )

    # Behind Nginx / Railway / Render, Django sees plain HTTP on the inside of
    # the proxy. Without this it believes every request is insecure and
    # SECURE_SSL_REDIRECT above sends the browser into an infinite redirect
    # loop. The proxy must be the one setting this header.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Django 4+ requires the scheme here, e.g. https://farm.example.com
    CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')

# Allowed hosts. Set DJANGO_ALLOWED_HOSTS in production, e.g.
#   DJANGO_ALLOWED_HOSTS=farm.example.com,www.farm.example.com
# Django rejects every request whose Host header is not listed, so an empty
# list in production means a site that answers nothing but HTTP 400.
ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS') or ['127.0.0.1', 'localhost']

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
    "django.contrib.sitemaps",

    # Project apps
    "detection",
    "blog",
    "contact",
    "features",
    "marketplace",
    "agrolease",
    "iot_sensor",
    "core",
    "accounts",
]

# ======================================================
# 5. MIDDLEWARE
# ======================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files directly from Gunicorn, so a deploy does not
    # need Nginx configured for /static/ before it will work. Must sit directly
    # after SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "core.context_processors.site_meta",
                "core.context_processors.company",
                "agrolease.context_processors.admin_summary",
                "blog.context_processors.blog_sidebar",
            ],
        },
    },
]

# ======================================================
# 8. DATABASE
# ======================================================
# SQLite is the default so a fresh clone runs with no setup. It serialises every
# write and will raise "database is locked" once several sensor nodes POST
# readings at the same time, so production must set DATABASE_URL to PostgreSQL.
#
#   DATABASE_URL=postgres://user:password@host:5432/dbname
#
# Parsed with urllib rather than adding a dj-database-url dependency.
def _database_from_url(url):
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    engines = {
        'postgres': 'django.db.backends.postgresql',
        'postgresql': 'django.db.backends.postgresql',
        'mysql': 'django.db.backends.mysql',
        'sqlite': 'django.db.backends.sqlite3',
    }
    scheme = parsed.scheme.split('+')[0]
    if scheme not in engines:
        raise ImproperlyConfigured(
            f"Unsupported DATABASE_URL scheme '{parsed.scheme}'. "
            f"Expected one of: {', '.join(sorted(engines))}."
        )
    if scheme == 'sqlite':
        return {'ENGINE': engines[scheme], 'NAME': parsed.path.lstrip('/') or ':memory:'}

    name = parsed.path.lstrip('/')
    if not name:
        raise ImproperlyConfigured('DATABASE_URL is missing a database name.')
    config = {
        'ENGINE': engines[scheme],
        'NAME': name,
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname or '',
        'PORT': str(parsed.port or ''),
        # Reuse connections for 10 minutes instead of opening one per request.
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '600')),
    }
    if os.getenv('DB_REQUIRE_SSL', 'True').lower() == 'true':
        config['OPTIONS'] = {'sslmode': 'require'}
    return config


DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL:
    DATABASES = {'default': _database_from_url(DATABASE_URL)}
else:
    if not DEBUG:
        import warnings
        warnings.warn(
            'Running with DEBUG=False on SQLite. Concurrent sensor ingest will '
            'hit "database is locked". Set DATABASE_URL to PostgreSQL.',
            RuntimeWarning,
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


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

# In production WhiteNoise serves compressed, hash-named copies so browsers can
# cache them forever. Left off in DEBUG because the manifest only exists after
# collectstatic has run, and a missing entry raises at render time.
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# ======================================================
# 12. MEDIA FILES (User Uploads)
# ======================================================
MEDIA_URL = "/media/"
# Where uploaded photos live. Configurable because in production this should
# point at a mounted volume OUTSIDE the repository: media inside the checkout
# is one `git clean` or one ephemeral-filesystem deploy away from deletion, and
# Ask AI re-reads the stored photo to answer follow-up questions, so losing it
# breaks every past diagnosis rather than just the gallery.
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "").strip() or (BASE_DIR / "media")

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

# Kindwise crop.health (primary crop disease diagnosis)
# Covers 23 major crops incl. rice, wheat, cotton, sugarcane - the staples the
# bundled 38-class PlantVillage model does not have. Keys: admin.kindwise.com
CROP_HEALTH_API_KEY = os.getenv("CROP_HEALTH_API_KEY", "").strip()
CROP_HEALTH_ENABLED = (
    os.getenv("CROP_HEALTH_ENABLED", "True") == "True" and bool(CROP_HEALTH_API_KEY)
)
CROP_HEALTH_BASE_URL = os.getenv("CROP_HEALTH_BASE_URL", "https://crop.kindwise.com")
CROP_HEALTH_TIMEOUT = float(os.getenv("CROP_HEALTH_TIMEOUT", "12"))
CROP_HEALTH_LANGUAGE = os.getenv("CROP_HEALTH_LANGUAGE", "en")
if not CROP_HEALTH_API_KEY:
    import warnings
    warnings.warn(
        "CROP_HEALTH_API_KEY not set in .env - disease diagnosis falls back to "
        "the bundled 38-class PlantVillage model, which covers no rice, wheat, "
        "cotton, sugarcane, chilli, banana or pulses. Get a key from: "
        "https://admin.kindwise.com",
        RuntimeWarning
    )

# ======================================================
# PAGE TRANSLATION
# ======================================================
# Used by core/translation.py. All providers are free and unreliable in
# different ways - see that module's docstring before relying on this.
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "")
LIBRETRANSLATE_TIMEOUT = int(os.getenv("LIBRETRANSLATE_TIMEOUT", "12"))
# How long a translated string is cached. Page text rarely changes, so a day
# is conservative; the cache is what keeps this feature usable at all.
TRANSLATION_CACHE_TIMEOUT = int(os.getenv("TRANSLATION_CACHE_TIMEOUT", str(60 * 60 * 24)))
# True skips the LibreTranslate batch attempt. Public LibreTranslate instances
# now mostly require an API key, so trying them first just adds latency.
TRANSLATION_FAST_MODE = os.getenv("TRANSLATION_FAST_MODE", "True").lower() == "true"
TRANSLATION_FALLBACK_WORKERS = int(os.getenv("TRANSLATION_FALLBACK_WORKERS", "10"))

# Translated strings are cached in their OWN alias, not in `default`.
#
# They genuinely need to outlive a restart: every string is paid for once at a
# real provider and then served free, and LocMemCache - the Django default - is
# per-process, so it empties on each restart and each gunicorn worker keeps a
# separate copy.
#
# `default` deliberately stays in-memory. It holds the SiteSettings model
# instance, and a pickled model in a shared, persistent cache is a trap: after
# a migration adds a field, the stale instance raises DoesNotExist the moment
# that field is touched, and it also leaks across the test-database boundary.
# Durable string cache, ephemeral object cache.
_REDIS_URL = os.getenv("REDIS_URL", "").strip()

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "translations": (
        {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_URL,
            "TIMEOUT": TRANSLATION_CACHE_TIMEOUT,
        }
        if _REDIS_URL
        else {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(BASE_DIR / ".cache" / "translations"),
            "TIMEOUT": TRANSLATION_CACHE_TIMEOUT,
            "OPTIONS": {"MAX_ENTRIES": 50000},
        }
    ),
}

# ======================================================
# COMPANY IDENTITY (legal pages + contact page read from here)
# ======================================================
# One source of truth. The privacy policy, terms and contact page all render
# from these, so the published details can never drift apart - and deploying to
# a new host only means setting COMPANY_HOSTING_PROVIDER, not editing templates.
COMPANY_NAME = os.getenv("COMPANY_NAME", "The Sensing Squad Agritech Pvt. Ltd.")
COMPANY_SHORT_NAME = os.getenv("COMPANY_SHORT_NAME", "AI Crop Health")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "Kolkata, West Bengal, India")
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "harekrishnahareramramram108@gmail.com")
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "").strip()
COMPANY_JURISDICTION = os.getenv("COMPANY_JURISDICTION", "India")
COMPANY_COURTS_CITY = os.getenv("COMPANY_COURTS_CITY", "Kolkata, West Bengal")

# Filled in automatically on deployment: set COMPANY_HOSTING_PROVIDER in the
# host's environment and the privacy policy updates itself. Until then it says
# so honestly rather than naming a provider that is not being used.
COMPANY_HOSTING_PROVIDER = os.getenv(
    "COMPANY_HOSTING_PROVIDER",
    "our own systems (not yet deployed to a third-party host)",
)

# Date shown as "last updated" on the legal pages.
COMPANY_POLICY_UPDATED = os.getenv("COMPANY_POLICY_UPDATED", "6 October 2026")

# Kindwise insect.id (insect / invertebrate identification)
# 14,000+ taxa, ~92% top-3 accuracy. Identification only - the app never turns
# an identified insect into a spray recommendation. Keys: admin.kindwise.com
INSECT_ID_API_KEY = os.getenv("INSECT_ID_API_KEY", "").strip()
INSECT_ID_ENABLED = (
    os.getenv("INSECT_ID_ENABLED", "True") == "True" and bool(INSECT_ID_API_KEY)
)
INSECT_ID_BASE_URL = os.getenv("INSECT_ID_BASE_URL", "https://insect.kindwise.com")
INSECT_ID_TIMEOUT = float(os.getenv("INSECT_ID_TIMEOUT", "12"))
INSECT_ID_LANGUAGE = os.getenv("INSECT_ID_LANGUAGE", "en")

# Groq (powers Ask AI follow-up questions on a diagnosis)
# Keys: https://console.groq.com/keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "30"))
# Image-capable. Groq lists no PRODUCTION vision model as of Oct 2026 - this one
# is in their preview tier, so Ask AI falls back to GROQ_TEXT_MODEL (production,
# text-only) if it is withdrawn. Change these here, not in code.
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
# Gemini model for the chatbot's second provider. gemini-1.5-flash-8b was
# hardcoded throughout and is retired - every Gemini call 404'd. Verified
# working on this key: gemini-2.5-flash.
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
if not GROQ_API_KEY:
    import warnings
    warnings.warn(
        "GROQ_API_KEY not set in .env - the Ask AI assistant on the diagnosis "
        "page will return an error instead of answering. Get a key from: "
        "https://console.groq.com/keys",
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
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "").strip() or (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "").strip() or "noreply@example.com"
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
            # Rotating, so the log cannot grow until it fills the disk and takes
            # the site down with it. 5 files x 5MB = 25MB ceiling.
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            # Without this the handler uses the OS locale encoding (cp1252 on
            # Windows) and ANY non-ASCII character in a log record raises
            # UnicodeEncodeError from inside logging.
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "features": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "detection": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "iot_sensor": {
            "handlers": ["console", "file"],
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


# ======================================================
# 15. SITE IDENTITY, SOCIAL PROFILES, SEO
# ======================================================
SITE_NAME = os.getenv('SITE_NAME', 'AI Crop Health')
SITE_TAGLINE = os.getenv(
    'SITE_TAGLINE',
    'AI crop disease diagnosis, land leasing and IoT field monitoring for farmers',
)

# Social profile URLs. Blank means "we do not have one" and the icon is hidden,
# rather than rendering a link that goes nowhere.
# The topbar and footer render whatever is filled in here, in the order set by
# core.context_processors.SOCIAL_ICON_META. Adding a network is an entry in
# both places - never a template edit. (Before this, `whatsapp` was listed here
# but the markup hardcoded five networks and silently ignored it.)
SOCIAL_LINKS = {
    'facebook': os.getenv('SOCIAL_FACEBOOK', ''),
    'twitter': os.getenv('SOCIAL_TWITTER', ''),
    'instagram': os.getenv('SOCIAL_INSTAGRAM', ''),
    'linkedin': os.getenv('SOCIAL_LINKEDIN', ''),
    'youtube': os.getenv('SOCIAL_YOUTUBE', ''),
    # Accepts a wa.me URL or a bare phone number, which is what people reach
    # for; a bare number is turned into a real wa.me link by the context
    # processor rather than becoming a dead relative href.
    'whatsapp': os.getenv('SOCIAL_WHATSAPP', ''),
    'telegram': os.getenv('SOCIAL_TELEGRAM', ''),
    'github': os.getenv('SOCIAL_GITHUB', ''),
}

# Image used for og:image / twitter:image link previews. Must be a path under
# STATIC_URL; the context processor makes it absolute, which crawlers require.
# Recommended: 1200x630 PNG or JPG, under 1MB.
SOCIAL_PREVIEW_IMAGE = os.getenv('SOCIAL_PREVIEW_IMAGE', STATIC_URL + 'assets/img/social-preview.png')


# ======================================================
# 16. ANALYTICS (optional, consent-gated)
# ======================================================
# Deliberately NOT Google Analytics by default: it requires a consent banner in
# many jurisdictions and sends visitor data to a third party. A cookieless,
# self-hostable option (Plausible, Umami, Fathom) avoids both problems.
# Blank disables analytics entirely.
#   ANALYTICS_SCRIPT_URL=https://plausible.io/js/script.js
#   ANALYTICS_SITE_ID=farm.example.com
ANALYTICS_SCRIPT_URL = os.getenv('ANALYTICS_SCRIPT_URL', '').strip()
ANALYTICS_SITE_ID = os.getenv('ANALYTICS_SITE_ID', '').strip()


# ======================================================
# 17. ERROR TRACKING (optional)
# ======================================================
# Enabled only when SENTRY_DSN is set, so nothing changes locally and the
# dependency stays optional. With real farmers on the system you want to hear
# about a 500 from the error tracker, not from the farmer.
#
#   pip install "sentry-sdk[django]"
#   SENTRY_DSN=https://...ingest.sentry.io/...
SENTRY_DSN = os.getenv('SENTRY_DSN', '').strip()
if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=os.getenv('SENTRY_ENVIRONMENT', 'production' if not DEBUG else 'development'),
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            # Farmer phone numbers, KYC documents and GPS coordinates pass
            # through this app. Do not ship personally identifying data to a
            # third party by default.
            send_default_pii=False,
        )
    except ImportError:
        import warnings

        warnings.warn(
            'SENTRY_DSN is set but sentry-sdk is not installed. '
            'Run: pip install "sentry-sdk[django]"',
            RuntimeWarning,
        )


# ======================================================
# PRODUCTION SAFETY CHECKS
# ======================================================
# Run only when DEBUG is off, i.e. on a real deployment. Each of these is a
# mistake that does not announce itself: the site comes up, looks fine, and is
# quietly insecure or broken. Failing to start is the kinder outcome - a deploy
# that refuses costs minutes, a leaked SECRET_KEY costs the whole system.
if not DEBUG:
    _problems = []

    # Django's own generator produces 50 characters. A short key weakens every
    # session cookie, password reset token and signed value on the site.
    if len(SECRET_KEY or '') < 50:
        _problems.append(
            'SECRET_KEY is {0} characters; it must be at least 50. Generate one with:\n'
            '    python -c "from django.core.management.utils import '
            'get_random_secret_key; print(get_random_secret_key())"'.format(
                len(SECRET_KEY or ''))
        )

    # With DEBUG off and no hosts listed, Django answers 400 to every request
    # and the site looks dead for reasons nothing in the logs explains well.
    if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['127.0.0.1', 'localhost']:
        _problems.append(
            'DJANGO_ALLOWED_HOSTS does not list the real domain. Set it to your '
            'host(s), e.g. DJANGO_ALLOWED_HOSTS=crophealth.in,www.crophealth.in'
        )

    # SQLite on a single file is fine locally and a liability in production:
    # one writer at a time, and on most hosts the file sits on a disk that is
    # replaced on the next deploy, taking every diagnosis and account with it.
    if 'sqlite' in DATABASES['default']['ENGINE']:
        _problems.append(
            'DATABASE_URL is not set, so the app is running on SQLite. Point it '
            'at PostgreSQL before taking real traffic.'
        )

    if EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
        _problems.append(
            'EMAIL_BACKEND is set to the console backend. Configure a production '
            'email backend so one-time login codes are not written to logs.'
        )
    elif EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
        if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            _problems.append(
                'SMTP email is enabled but EMAIL_HOST_USER or '
                'EMAIL_HOST_PASSWORD is missing.'
            )
        if DEFAULT_FROM_EMAIL == 'noreply@example.com':
            _problems.append(
                'Set DEFAULT_FROM_EMAIL to a sender address verified by your '
                'email provider.'
            )

    # The diagnosis images are not decoration: Ask AI re-reads the stored photo
    # to answer follow-up questions, so losing MEDIA_ROOT breaks that feature
    # for every past diagnosis, and the DiagnosisLog rows point at nothing.
    if not os.getenv('MEDIA_ROOT') and not os.getenv('AWS_STORAGE_BUCKET_NAME'):
        import warnings
        warnings.warn(
            'MEDIA_ROOT is the default path inside the project directory. On a '
            'host with an ephemeral filesystem every uploaded photo is deleted '
            'on the next deploy. Mount a volume and set MEDIA_ROOT to it, or '
            'configure object storage.',
            RuntimeWarning,
        )

    if _problems:
        raise ImproperlyConfigured(
            'Refusing to start in production with these problems:\n\n  - '
            + '\n\n  - '.join(_problems)
            + '\n\nSet them in the environment, or run with DJANGO_DEBUG=True '
              'for local development.'
        )
