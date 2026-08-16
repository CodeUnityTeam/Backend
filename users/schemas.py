from typing import Any

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
)
from rest_framework import serializers

from users.serializers.profile import MeProfileRetrieveSerializer

# ------------------ Сериализаторы для Swagger-документации ------------------


class SocialAuthQueryParamsSerializer(serializers.Serializer):
    """Сериализатор входящих Query-параметров от OAuth-провайдера.

    Описывает параметры строки запроса, которые бэкенд перехватывает
    в GET-сценарии автоматического редиректа.
    """

    code = serializers.CharField(
        required=True,
        help_text=(
            'Временный код авторизации (Authorization Code), выданный '
            'сервером провайдера. Обменивается бэкендом на JWT-токены.'
        ),
    )
    state = serializers.CharField(
        required=False,
        help_text=(
            'Уникальная строка состояния (OAuth2 state token). '
            'Используется для защиты от CSRF-атак и сохранения '
            'контекста состояния на клиенте.'
        ),
    )


class SocialAuthErrorSerializer(serializers.Serializer):
    """Сериализатор для отображения ошибок валидации и сети."""

    non_field_errors = serializers.ListField(
        child=serializers.CharField(),
        help_text='Список общих ошибок авторизации модуля соцсетей.',
    )


class SocialLoginSuccessResponseSerializer(serializers.Serializer):
    """Схема успешного ответа при обмене кода авторизации на JWT."""

    access = serializers.CharField(
        help_text='JWT access токен для аутентификации запросов.',
    )
    refresh = serializers.CharField(
        help_text='JWT refresh токен для обновления access токена.',
    )
    user = MeProfileRetrieveSerializer()
    access_expiration = serializers.DateTimeField(
        help_text='Дата и время истечения access токена.',
    )
    refresh_expiration = serializers.DateTimeField(
        help_text='Дата и время истечения refresh токена.',
    )


SOCIAL_LOGIN_REDIRECT_SCHEMA: Any = OpenApiResponse(
    response=None,
    description=(
        '### Область применения\n'
        'Данный метод применяется в случае, если в конфигурации '
        'сервера (`settings.py`) для соответствующего провайдера '
        'в качестве `CALLBACK_URL` указан эндпоинт бэкенда API.\n\n'
        '### Протокол взаимодействия\n'
        '1. Пользователь проходит аутентификацию на стороне '
        'внешнего провайдера (Google, Yandex, Mail.ru).\n'
        '2. Внешний провайдер перенаправляет браузер пользователя '
        'на данный эндпоинт бэкенда, передавая параметр `code` '
        'в строке запроса (Query Parameters).\n'
        '3. Сервер производит обмен кода авторизации на JWT-токены '
        'и выполняет HTTP-перенаправление (код 302) обратно на '
        'сторону фронтенд-приложения.\n\n'
        '### Формат выходных данных\n'
        'Перенаправление пользователя осуществляется на адрес:\n'
        '`{HOST_URL}/auth/callback?access=TOKEN&refresh=TOKEN`\n'
        'Дополнительно в заголовках ответа устанавливаются '
        'авторизационные куки (согласно общесистемным настройкам JWT).'
    ),
)

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

POST_SCENARIO_DESCRIPTION: str = (
    '### Область применения\n'
    'Данный метод применяется в случае, если в конфигурации '
    'сервера (`settings.py`) для соответствующего провайдера '
    'в качестве `CALLBACK_URL` указан прямой адрес '
    'клиентского (фронтенд) приложения.\n\n'
    '### Протокол взаимодействия\n'
    '1. Пользователь проходит аутентификацию на стороне '
    'внешнего провайдера.\n'
    '2. Провайдер перенаправляет пользователя на фронтенд-приложение '
    '(например: `https://domain.com`).\n'
    '3. Клиентское приложение извлекает параметр `code` из URL.\n'
    '4. Клиентское приложение отправляет POST-запрос с JSON-телом, '
    'содержащим `code`, на данный эндпоинт API.\n\n'
    '### Формат выходных данных\n'
    'Сервер возвращает структуру данных, содержащую JWT-токены '
    'непосредственно в теле ответа (JSON).'
)
