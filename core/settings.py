import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')
DEBUG      = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'planner',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Dubai'
USE_I18N      = True
USE_TZ        = True

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Auth
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/sm/panel/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_AGE  = 86400 * 7  # 7 days

# Email — console for now, SendGrid in Task 2
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Resend email
RESEND_API_KEY     = os.environ.get('RESEND_API_KEY', '')
DEFAULT_FROM_EMAIL = 'SprintFlow <noreply@contact.getsprintflow.co>'
EMAIL_BACKEND      = 'django.core.mail.backends.console.EmailBackend'  # fallback if no key

# Auth
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/sm/panel/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_AGE  = 86400 * 7

# App URL — used in emails
APP_URL = os.environ.get('APP_URL', 'https://getsprintflow.co')

# Paddle
PADDLE_API_KEY           = os.environ.get('PADDLE_API_KEY', '')
PADDLE_WEBHOOK_SECRET    = os.environ.get('PADDLE_WEBHOOK_SECRET', '')
PADDLE_ENVIRONMENT       = os.environ.get('PADDLE_ENVIRONMENT', 'sandbox')

PADDLE_PRICES = {
    'starter_monthly':  os.environ.get('PADDLE_STARTER_MONTHLY', ''),
    'starter_annual':   os.environ.get('PADDLE_STARTER_ANNUAL', ''),
    'pro_monthly':      os.environ.get('PADDLE_PRO_MONTHLY', ''),
    'pro_annual':       os.environ.get('PADDLE_PRO_ANNUAL', ''),
    'business_monthly': os.environ.get('PADDLE_BUSINESS_MONTHLY', ''),
    'business_annual':  os.environ.get('PADDLE_BUSINESS_ANNUAL', ''),
}

# Plan limits
PLAN_LIMITS = {
    'starter': {
        'members':          10,
        'teams':            1,
        'sessions_per_month': 5,
        'excel':            False,
        'backlog':          False,
        'ai':               False,
        'analytics':        False,
    },
    'pro': {
        'members':          30,
        'teams':            5,
        'sessions_per_month': None,  # unlimited
        'excel':            True,
        'backlog':          True,
        'ai':               False,
        'analytics':        False,
    },
    'business': {
        'members':          None,  # unlimited
        'teams':            None,
        'sessions_per_month': None,
        'excel':            True,
        'backlog':          True,
        'ai':               True,
        'analytics':        True,
    },
}
