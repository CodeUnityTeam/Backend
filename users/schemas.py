from typing import Any

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
)
from rest_framework import serializers

# --- Сериализаторы для Swagger-документации ---


class SocialAuthQueryParamsSerializer(serializers.Serializer):
    """Сериализатор для входящих параметров от OAuth-провайдера.

    Описывает обязательные Query-параметры, которые бэкенд
    ожидает перехватить в URL-строке GET-запроса редиректа.
    """

    code = serializers.CharField(
        required=True,
        help_text='Временный код авторизации от OAuth-провайдера.',
    )
    state = serializers.CharField(
        required=False,
        help_text='Защитный статус-токен для предотвращения CSRF-атак.',
    )


class SocialAuthErrorSerializer(serializers.Serializer):
    """Сериализатор для отображения ошибок валидации и сети."""

    non_field_errors = serializers.ListField(
        child=serializers.CharField(),
        help_text='Список общих ошибок авторизации модуля соцсетей.',
    )


# --- Финальные схемы ответов (Responses) ---

# Схема для успешной авторизации (302 Redirect): Тело ответа отсутствует
SOCIAL_LOGIN_REDIRECT_SCHEMA: Any = OpenApiResponse(
    response=None,
    description=(
        'Успешная авторизация. Бэкенд возвращает HTTP 302 Redirect '
        'и перенаправляет браузер на фронтенд (/auth/callback). '
        'Параметры access и refresh передаются в URL-строке редиректа. '
        'Параллельно бэкенд устанавливает Secure HttpOnly куки.'
    ),
)

# Схема для ошибок (400 Bad Request): Валидный JSON с примерами сценариев
SOCIAL_LOGIN_ERROR_SCHEMA: Any = OpenApiResponse(
    response=SocialAuthErrorSerializer,
    description=(
        'Ошибка валидации переданного кода авторизации '
        'или сбой сетевого соединения со сторонним провайдером.'
    ),
    examples=[
        OpenApiExample(
            name='Неверный или истекший код',
            value={
                'non_field_errors': [
                    'Не удалось авторизоваться через '
                    'социальную сеть. Неверный или '
                    'истекший code.',
                ],
            },
        ),
        OpenApiExample(
            name='Сбой сети (Таймаут провайдера)',
            value={
                'non_field_errors': [
                    'Внешний сервис авторизации временно '
                    'недоступен. Пожалуйста, попробуйте '
                    'позже.',
                ],
            },
        ),
    ],
)
