import logging.config
import logging.handlers
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

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

INSTALLED_APPS = (
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
    'core.apps.CoreConfig',
    'users.apps.UsersConfig',
    'projects.apps.ProjectsConfig',
    'qna.apps.QnaConfig',
    'feedback.apps.FeedbackConfig',
    'help.apps.HelpConfig',
)

MIDDLEWARE = (
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'users.middleware.UpdateLastActivityMiddleware',
)

TEMPLATES = (
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': (
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ),
        },
    },
)

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
S3_PUBLIC_URL = os.getenv('S3_PUBLIC_URL', '').rstrip('/')

# Протокол для публичных URL (http: или https:).
# По умолчанию S3Boto3Storage использует "https:", что ломает локальную
# разработку, где MinIO работает по HTTP.
# В продакшене через nginx проксирование — всегда https:.
AWS_S3_URL_PROTOCOL = os.getenv('AWS_S3_URL_PROTOCOL', 'https:')

# Кастомный домен для публичных URL файлов (без протокола).
# Используется nginx для прокси на MinIO.
# Пример: "dev.code-unity.ru/media"
S3_CUSTOM_DOMAIN = (
    S3_PUBLIC_URL.replace('http://', '').replace('https://', '')
    if S3_PUBLIC_URL
    else S3_ENDPOINT.replace('http://', '').replace('https://', '')
)

# Имена бакетов для каждого типа медиа.
# Ключи должны соответствовать значениям MediaType из core.s3_utils.
S3_BUCKETS = {
    'avatars': os.getenv('AVATARS_BUCKET', 'user-avatars'),
    'questions': os.getenv('QUESTION_IMAGES_BUCKET', 'question-images'),
    'answers': os.getenv('ANSWER_IMAGES_BUCKET', 'answer-images'),
    'feedback': os.getenv('FEEDBACK_IMAGES_BUCKET', 'feedback-images'),
    'projects': os.getenv('PROJECT_IMAGES_BUCKET', 'project-images'),
    'images': os.getenv('UPLOAD_IMAGES_BUCKET', 'upload-images'),
}

# Максимальный размер файла для всех типов (в MB)
S3_MAX_FILE_SIZE_MB = 10

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
    's3': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        'OPTIONS': {
            'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'endpoint_url': S3_ENDPOINT,
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

# =============================================================================
# SECURITY, CORS & AUTH MODEL
# =============================================================================

AUTH_USER_MODEL = 'users.User'
SITE_ID = 1

CORS_ALLOWED_ORIGINS = TRUSTED_ORIGINS

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

AUTH_PASSWORD_VALIDATORS = (
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
)

# =============================================================================
# DJANGO REST FRAMEWORK CONFIGURATION
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.AllowAny',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'dj_rest_auth.jwt_auth.JWTCookieAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
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
    'OLD_PASSWORD_FIELD_ENABLED': True,
    'LOGIN_SERIALIZER': 'users.serializers.auth.CustomLoginSerializer',
    'PASSWORD_CHANGE_SERIALIZER': (
        'users.serializers.auth.CustomPasswordChangeSerializer'
    ),
    'PASSWORD_RESET_SERIALIZER': (
        'users.serializers.auth.CustomPasswordResetSerializer'
    ),
    'PASSWORD_RESET_CONFIRM_SERIALIZER': (
        'users.serializers.auth.CustomPasswordResetConfirmSerializer'
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

if os.getenv('PRODUCTION_EMAIL_BACKEND', 'False').lower() == 'true':
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

SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
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
    'COMPONENT_SPLIT_REQUEST': True,
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'jwt_cookie_auth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': (
                    'Авторизация dj_rest_auth. '
                    'Передайте токен в формате: Bearer <token>'
                ),
            },
        },
    },
    'TAG_SORT_ORDER': 'definition',
    'TAGS': (
        {'name': 'Questions', 'description': 'Вопросы'},
        {'name': 'Answers', 'description': 'Ответы'},
        {'name': 'Likes', 'description': 'Лайки'},
        {'name': 'Tags', 'description': 'Теги'},
        {'name': 'Files', 'description': 'Файлы'},
        {'name': 'Feedbacks', 'description': 'Обратная связь'},
        {'name': 'Reviews', 'description': 'Отзывы'},
    ),
}

# =============================================================================
# CACHE CONFIGURATION (Redis via django-redis)
# =============================================================================

REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = os.getenv('REDIS_PORT')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# Если пароль не задан — подключаемся без аутентификации
_REDIS_AUTH = f':{REDIS_PASSWORD}@' if REDIS_PASSWORD else ''

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{_REDIS_AUTH}{REDIS_HOST}:{REDIS_PORT}/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 3,
            },
            'MAX_CONNECTIONS': 1000,
            'PICKLE_VERSION': -1,
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'codeunity',
    },
    'local_memory': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'codeunity-local',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        },
    },
}

# Fallback при недоступности Redis
DJANGO_REDIS_IGNORE_EXCEPTIONS = True
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

# =============================================================================
# LOGGING
# =============================================================================


class MakeDirRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Хэндлер, создающий папку для логов перед инициализацией."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Извлекаем имя файла из аргументов dictConfig."""
        filename = kwargs.get('filename', args[0] if args else '')
        log_dir = os.path.dirname(str(filename))

        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        super().__init__(*args, **kwargs)


class ParentDirFilter(logging.Filter):
    """Фильтр для добавления имени каталога исходного кода в лог."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Добавляет parent_dir — имя каталога, где лежит .py файл."""
        if record.pathname:
            record.parent_dir = os.path.basename(
                os.path.dirname(record.pathname),
            )
        else:
            record.parent_dir = ''
        return True


config = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'add_parent_dir': {
            '()': ParentDirFilter,
        },
    },
    'formatters': {
        'simple': {'format': (
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
        )},
        'detailed': {
            'format': (
                '%(asctime)s - [%(levelname)s] - %(name)s '
                '%(parent_dir)s/%(filename)s:'
                '%(funcName)s:%(lineno)d - %(message)s'
            ),
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'simple',
        },
        'file': {
            'class': MakeDirRotatingFileHandler,
            'level': 'WARNING',
            'filename': os.path.join(BASE_DIR, 'logs', 'logs.log'),
            'formatter': 'detailed',
            'filters': ['add_parent_dir'],
            'mode': 'a',
            'encoding': 'utf-8',
            'maxBytes': 5242880,
            'backupCount': 3,
        },
    },
    'loggers': {
        # логгеры приложений
        'core': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
        'users': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
        'projects': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
        'qna': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
        'feedback': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
        'help': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
        # стандартные django-логгеры
        'django.request': {
            'level': 'ERROR',
            'handlers': ['file'],
            'propagate': False,
        },
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['file'],
            'propagate': False,
        },
        'django.security': {
            'level': 'WARNING',
            'handlers': ['file'],
            'propagate': False,
        },
    },
    # корневой логгер
    'root': {
        'level': 'WARNING',
        'handlers': ['console', 'file'],
    },
}

logging.config.dictConfig(config)
