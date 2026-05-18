# flake8: noqa
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SPECTACULAR_SETTINGS = {
    'TITLE': 'CodeUnity',
    'DESCRIPTION': "Platform for project's and developer's unity",
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TERMS_OF_SERVICE': '',
    'CONTACT': {'name': '', 'email': ''},
    'LICENSE': {'name': ''}, 
}

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = os.getenv("DEBUG_MODE", default="False").lower() == "true"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

#  DOMAIN = os.getenv('DOMAIN')

# CSRF_TRUSTED_ORIGINS = [os.getenv('CSRF_DOMAIN'),]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    'drf_spectacular',
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.mailru",
    "allauth.socialaccount.providers.yandex",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "rest_framework_simplejwt",
    "corsheaders",
    "users.apps.AuthConfig",
    "projects.apps.ProjectsConfig",
    "qna.apps.QnaConfig",
    "feedback.apps.FeedbackConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Определение хоста БД в зависимости от режима
DB_MODE = os.getenv("DB_MODE")
if DB_MODE == "local":
    DB_HOST = os.getenv("DB_HOST_LOCAL")
else:
    DB_HOST = os.getenv("DB_HOST")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": DB_HOST,
        "PORT": os.getenv("DB_PORT"),
    }
}

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

LANGUAGE_CODE = "ru-RU"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AUTH_USER_MODEL = 'users.User'

CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": "access-token",
    "JWT_AUTH_REFRESH_COOKIE": "refresh-token",
    "JWT_AUTH_HTTPONLY": True,
    "JWT_AUTH_SECURE": False,  # Set True in production
    "JWT_AUTH_SAMESITE": "Lax",
    "JWT_AUTH_RETURN_EXPIRATION": True,
    "SESSION_LOGIN": False,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# Настройки dj-rest-auth для стандартной авторизации
ACCOUNT_SIGNUP_FIELDS = ["firstname*", "lastname*", "email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {"email"}

# Настройки dj-rest-auth для авторизации черех сторонние сервисы
SOCIALACCOUNT_ADAPTER = "allauth.socialaccount.adapter.DefaultSocialAccountAdapter"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "secret": os.getenv("GOOGLE_SECRET"),
            "key": "",
        },
        "SCOPE": [
            "profile",
            "email",
        ],
        "VERIFIED_EMAIL": True,
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "CALLBACK_URL": os.getenv("GOOGLE_CALLBACK_URL"),
    },
    "yandex": {
        "APP": {
            "client_id": os.getenv("YANDEX_CLIENT_ID"),
            "secret": os.getenv("YANDEX_SECRET"),
            "key": "",
        },
        "SCOPE": [
            "login:email",
            "login:info",
            "login:avatar",
        ],
        "VERIFIED_EMAIL": True,
        "AUTH_PARAMS": {
            "display": "popup",
        },
        "CALLBACK_URL": os.getenv("YANDEX_CALLBACK_URL"),
    },
    "mailru": {
        "APP": {
            "client_id": os.getenv("MAILRU_CLIENT_ID"),
            "secret": os.getenv("MAILRU_SECRET"),
            "key": "",
        },
        "SCOPE": [
            "userinfo",
            "email",
        ],
        "VERIFIED_EMAIL": True,
        "AUTH_PARAMS": {
            "response_type": "code",
        },
        "METHOD": "oauth2",
        "VERIFIED_EMAIL": True,
        "CALLBACK_URL": os.getenv("MAILRU_CALLBACK_URL"),
    },
}

SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_REQUIRED = True
