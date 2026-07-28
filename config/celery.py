import json
import os
from typing import Any

import django
from celery import Celery
from kombu.serialization import register

# Инициализируем окружение Django до импорта тасок и моделей
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.db.models import Model  # noqa: E402
from django.http import HttpRequest  # noqa: E402

# =============================================================================
# КАСТОМНЫЙ СЕРИАЛИЗАТОР ДЛЯ КОНТЕКСТА DJANGO (DJANGO_JSON)
# =============================================================================


class CeleryContextJSONEncoder(json.JSONEncoder):
    """Автоматически переводит модели Django в безопасный для JSON формат."""

    def default(self, obj: Any) -> Any:
        """Определяет кастомную логику сериализации для объектов Django."""
        if isinstance(obj, Model):
            return {
                '__django_model__': True,
                'app_label': obj._meta.app_label,
                'model_name': obj._meta.model_name,
                'pk': str(obj.pk),
            }
        if isinstance(obj, HttpRequest):
            return None
        return super().default(obj)


def celery_context_json_decoder(obj: Any) -> Any:
    """Автоматически восстанавливает живые инстансы моделей из базы данных."""
    if isinstance(obj, dict) and '__django_model__' in obj:
        from django.apps import apps
        model = apps.get_model(obj['app_label'], obj['model_name'])
        return model.objects.filter(pk=obj['pk']).first()
    return obj


def register_custom_serializer() -> None:
    """Регистрирует кастомный тип сериализации в экосистеме Kombu/Celery."""
    register(
        'django_json',
        lambda obj: json.dumps(obj, cls=CeleryContextJSONEncoder),
        lambda string: json.loads(
            string, object_hook=celery_context_json_decoder,
        ),
        content_type='application/x-django-json',
        content_encoding='utf-8',
    )


register_custom_serializer()

# =============================================================================
# ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ CELERY
# =============================================================================

# Переключаем хост редиса в зависимости от среды выполнения (Docker / Local)
if os.getenv('DB_MODE') == 'network':
    redis_host = settings.DOCKER_REDIS_HOST
else:
    redis_host = settings.REDIS_HOST

_REDIS_AUTH = (
    f':{settings.REDIS_PASSWORD}@' if settings.REDIS_PASSWORD else ''
)
redis_url: str = f'redis://{_REDIS_AUTH}{redis_host}:{settings.REDIS_PORT}/0'

celery_app = Celery(
    'TaskFlow',
    broker=redis_url,
    backend=redis_url,
    include=('core.tasks',),
)

# Переводим Celery на использование сериализатора
celery_app.conf.update(
    task_serializer='django_json',
    result_serializer='django_json',
    accept_content=['django_json', 'json'],
)
