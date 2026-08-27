import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",      # Vue frontend
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    'corsheaders',          
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'authentication',
    'monitoring.apps.MonitoringConfig',
    'ai_engine',
    'healing',
    'dashboard',
]

# ---------------------------------------------------------------------------
# Django REST Framework
# Default: token-based auth for the SPA dashboard client, IsAuthenticated by
# default (individual views loosen/tighten this via RBAC permission classes
# in authentication.permissions).
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# ---------------------------------------------------------------------------
# Security Requirement: 'User passwords shall be hashed using Bcrypt before
# storage.' BCryptSHA256PasswordHasher is listed first so it becomes the
# hasher used for all newly-set passwords; the PBKDF2 hasher remains
# available so Django can still verify/upgrade any pre-existing hashes.
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# ---------------------------------------------------------------------------
# Logging: structured [LEVEL] tag format used throughout the codebase
# (no emojis, per project convention).
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[%(levelname)s] %(asctime)s %(name)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'neurosynapse': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

MIDDLEWARE = [
     'corsheaders.middleware.CorsMiddleware', 
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,  # Wait up to 30 seconds for lock release
        },
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lusaka'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# When True (default), running `python manage.py runserver` automatically
# starts the telemetry collector and MAPE-K orchestrator as background
# threads (see monitoring/apps.py::MonitoringConfig.ready()). Set to False
# via the environment to run the dev server without these services, e.g.
# when driving them manually via `start_collector` / `start_orchestrator`.
# ---------------------------------------------------------------------------
NEUROSYNAPSE_AUTOSTART = os.getenv('NEUROSYNAPSE_AUTOSTART', 'True') == 'True'