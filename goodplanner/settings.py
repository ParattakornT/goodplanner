"""Local development settings. See README.txt before deploying publicly."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
# Everything the browser receives lives under web/: pages, partials, css, js.
WEB_DIR = BASE_DIR / 'web'
DATA_DIR.mkdir(exist_ok=True)
secret_file = DATA_DIR / '.django-secret-key'
if not os.environ.get('DJANGO_SECRET_KEY') and not secret_file.exists():
    try:
        with secret_file.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or secret_file.read_text(encoding='utf-8').strip()
DEBUG = os.environ.get('DJANGO_DEBUG') == '1'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
# Hosting platforms hand the public hostname over as an environment variable.
ALLOWED_HOSTS += [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if host.strip()]
# Django 4+ needs the https origin spelled out before it accepts a POST.
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('DJANGO_CSRF_ORIGINS', '').split(',') if origin.strip()]
# Render publishes the service's own hostname; trust it without extra setup.
RENDER_HOST = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append('https://' + RENDER_HOST)
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
                  'django.contrib.messages', 'django.contrib.staticfiles', 'planner']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'planner.middleware.ResponseHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]
ROOT_URLCONF = 'goodplanner.urls'
WSGI_APPLICATION = 'goodplanner.wsgi.application'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [WEB_DIR / 'pages', WEB_DIR], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                                                 'django.contrib.auth.context_processors.auth',
                                                 'django.contrib.messages.context_processors.messages']}}]
# Static files are only used by the admin site; WhiteNoise serves them in production.
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.environ.get('GOODPLANNER_DB', str(DATA_DIR / 'goodplanner-django.sqlite3')),
    # Serialize write transactions, including the check-and-create of meetings.
    'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'},
}}
# A managed Postgres keeps the data when the platform replaces the container.
# SQLite stays the default so local development needs no database server.
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres'):
    from urllib.parse import unquote, urlparse

    parsed = urlparse(DATABASE_URL)
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parsed.path.lstrip('/'),
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname or '',
        'PORT': str(parsed.port or ''),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {'sslmode': os.environ.get('PGSSLMODE', 'require')},
    }}
AUTH_USER_MODEL = 'planner.User'
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'planner.hashers.LegacyScryptPasswordHasher',
]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'th'
TIME_ZONE = 'Asia/Bangkok'
USE_TZ = True
APPEND_SLASH = False
SESSION_COOKIE_NAME = 'goodplanner_django_session'
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_NAME = 'goodplanner_csrftoken'
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_FAILURE_VIEW = 'planner.views.csrf_failure'
SESSION_COOKIE_SECURE = os.environ.get('DJANGO_HTTPS') == '1'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
if SESSION_COOKIE_SECURE:
    # The platform terminates TLS and forwards plain HTTP to this process.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
GOOGLE_CLIENT_ID = os.environ.get(
    'GOOGLE_CLIENT_ID',
    '1047176551743-79grbk0b4hukl43cnovh8qlliib372ej.apps.googleusercontent.com',
)
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '')
DATA_UPLOAD_MAX_MEMORY_SIZE = 16384
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

# Public address used in email links, e.g. https://goodplanner.onrender.com
SITE_URL = os.environ.get('SITE_URL', 'https://' + RENDER_HOST if RENDER_HOST else 'http://localhost:3000')
# Accounts listed here become admins (/admin) the next time they sign in.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()}
# Shared secret for the scheduled reminder call (GitHub Actions → /api/cron/reminders).
CRON_SECRET = os.environ.get('CRON_SECRET', '')
# Without a connected Gmail account, reminder emails are printed to the console.
EMAIL_BACKEND = os.environ.get('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = 'Good Planner <noreply@localhost>'
EMAIL_ASYNC = True
# On Render, never fall back to the console: unsent reminders are retried instead.
REQUIRE_GMAIL = bool(RENDER_HOST)
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'root': {'handlers': ['console'], 'level': 'WARNING'},
           'loggers': {'django.request': {'level': 'ERROR'}}}
