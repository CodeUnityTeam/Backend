import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# BASE CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG_MODE', default='False').lower() == 'true'

DOMAIN = os.getenv('DOMAIN')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

TRUSTED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',')
CSRF_TRUSTED_ORIGINS = TRUSTED_ORIGINS

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# CORE DJANGO APPS & MIDDLEWARE
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party packages
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.mailru',
    'allauth.socialaccount.providers.yandex',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'rest_framework_simplejwt',
    'corsheaders',
    # Project apps
    'users.apps.UsersConfig',
    'projects.apps.ProjectsConfig',
    'qna.apps.QnaConfig',
    'feedback.apps.FeedbackConfig',
    'help.apps.HelpConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# =============================================================================
# DATABASES & STORAGES (MINIO)
# =============================================================================

DB_MODE = os.getenv('DB_MODE')

if DB_MODE == 'local':
    DB_HOST = os.getenv('DB_HOST_LOCAL')
else:
    DB_HOST = os.getenv('DB_HOST')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': DB_HOST,
        'PORT': os.getenv('DB_PORT'),
    },
}

S3_ENDPOINT = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },

    'avatars': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        'OPTIONS': {
            'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'bucket_name': os.environ.get('AWS_STORAGE_BUCKET_NAME'),
            'endpoint_url': S3_ENDPOINT,  # Динамический хост
            'custom_domain': (
                f'{os.environ.get("S3_ENDPOINT")}'
                f'/{os.environ.get("AWS_STORAGE_BUCKET_NAME")}'
            ),
            'querystring_auth': False,
            'file_overwrite': False,
        },
    },
    'images': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        'OPTIONS': {
            'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'bucket_name': os.environ.get(
                'MINIO_IMAGES_BUCKET_NAME', 'images',
            ),
            'endpoint_url': S3_ENDPOINT,
            'custom_domain': (
                f'{os.environ.get("S3_ENDPOINT")}'
                f'{os.environ.get("MINIO_IMAGES_BUCKET_NAME", "images")}'
            ),
            'querystring_auth': False,
            'file_overwrite': False,
        },
    },
}

# =============================================================================
# INTERNATIONALIZATION, STATIC & MEDIA
# =============================================================================

LANGUAGE_CODE = 'ru-RU'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = '/backend_static/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

ALLOW_AVATAR_SIZE_MB = 10
ALLOW_IMAGE_SIZE_MB = 10

# =============================================================================
# SECURITY, CORS & AUTH MODEL
# =============================================================================

AUTH_USER_MODEL = 'users.User'
SITE_ID = 1

CORS_ALLOWED_ORIGINS = TRUSTED_ORIGINS

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.NumericPasswordValidator'
        ),
    },
]

# =============================================================================
# DJANGO REST FRAMEWORK CONFIGURATION
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'dj_rest_auth.jwt_auth.JWTCookieAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# =============================================================================
# DJ-REST-AUTH & SIMPLE JWT CONFIGURATION
# =============================================================================

REST_AUTH = {
    'USE_JWT': True,
    'SESSION_LOGIN': False,
    'USER_ID_FIELD': 'user_id',
    'JWT_AUTH_COOKIE': 'access-token',
    'JWT_AUTH_REFRESH_COOKIE': 'refresh-token',
    'JWT_AUTH_HTTPONLY': False,
    'JWT_AUTH_SECURE': False,
    'JWT_AUTH_SAMESITE': 'Lax',
    'JWT_AUTH_RETURN_EXPIRATION': True,
    'LOGIN_SERIALIZER': 'users.serializers.auth.CustomLoginSerializer',
    'PASSWORD_CHANGE_SERIALIZER': (
        'users.serializers.auth.CustomPasswordChangeSerializer'
    ),
    'PASSWORD_RESET_SERIALIZER': (
        'users.serializers.auth.CustomPasswordResetSerializer'
    ),
    'REGISTER_SERIALIZER': 'users.serializers.auth.CustomRegisterSerializer',
    'USER_DETAILS_SERIALIZER': (
        'users.serializers.profile.MeProfileRetrieveSerializer'
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'USER_ID_FIELD': 'user_id',
}

ACCOUNT_ADAPTER = 'users.adapters.CustomAccountAdapter'
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ('first_name*', 'last_name*', 'email*', 'password1*')
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# =============================================================================
# E-MAIL SERVER
# =============================================================================

DEFAULT_FROM_EMAIL = os.getenv('EMAIL_HOST_USER', 'hello@code-unity.ru')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
print
if os.getenv('PRODUCTION_EMAIL_BACKEND', False) is True:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 465))
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# =============================================================================
# SOCIAL AUTHENTICATION PROVIDERS
# =============================================================================

SOCIALACCOUNT_ADAPTER = (
    'allauth.socialaccount.adapter.DefaultSocialAccountAdapter'
)
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_REQUIRED = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_SECRET'),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'VERIFIED_EMAIL': True,
        'AUTH_PARAMS': {'access_type': 'online'},
        'CALLBACK_URL': os.getenv('GOOGLE_CALLBACK_URL'),
    },
    'yandex': {
        'APP': {
            'client_id': os.getenv('YANDEX_CLIENT_ID'),
            'secret': os.getenv('YANDEX_SECRET'),
            'key': '',
        },
        'SCOPE': ['login:email', 'login:info', 'login:avatar'],
        'VERIFIED_EMAIL': True,
        'AUTH_PARAMS': {'display': 'popup'},
        'CALLBACK_URL': os.getenv('YANDEX_CALLBACK_URL'),
    },
    'mailru': {
        'APP': {
            'client_id': os.getenv('MAILRU_CLIENT_ID'),
            'secret': os.getenv('MAILRU_SECRET'),
            'key': '',
        },
        'SCOPE': ['userinfo', 'email'],
        'VERIFIED_EMAIL': True,
        'AUTH_PARAMS': {'response_type': 'code'},
        'METHOD': 'oauth2',
        'CALLBACK_URL': os.getenv('MAILRU_CALLBACK_URL'),
    },
}

# =============================================================================
# SPECTACULAR API DOCUMENTATION
# =============================================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'CodeUnity',
    'DESCRIPTION': "Platform for project's and developer's unity",
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TERMS_OF_SERVICE': '',
    'CONTACT': {'name': '', 'email': ''},
    'LICENSE': {'name': ''},
    'TAG_SORT_ORDER': 'definition',
    'TAGS': [
        {'name': 'Questions', 'description': 'Вопросы'},
        {'name': 'Answers', 'description': 'Ответы'},
        {'name': 'Likes', 'description': 'Лайки'},
        {'name': 'Tags', 'description': 'Теги'},
        {'name': 'Files', 'description': 'Файлы'},
    ],
}
