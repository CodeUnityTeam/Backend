import logging
from typing import Any

from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.http import HttpRequest
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from users.schemas import (
    POST_SCENARIO_DESCRIPTION,
    SOCIAL_LOGIN_ERROR_SCHEMA,
    SOCIAL_LOGIN_REDIRECT_SCHEMA,
    SocialAuthQueryParamsSerializer,
    SocialLoginSuccessResponseSerializer,
)
from users.serializers.oauth import (
    SafeSocialLoginSerializer,
    SocialAuthCodeRequestSerializer,
    SocialAuthUrlResponseSerializer,
)
from users.services.oauth import (
    SocialAuthCallbackMixin,
    get_provider_config,
    social_auth_url_service,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Получить ссылку для авторизации через сторонний сервис',
        parameters=[
            OpenApiParameter(
                name='provider',
                type=str,
                location=OpenApiParameter.PATH,
                description='Имя провайдера (google, yandex, mailru)',
                required=True,
            ),
            OpenApiParameter(
                name='state',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Дополнительный параметр state для Yandex',
                required=False,
            ),
        ],
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class SocialAuthUrlView(APIView):
    """Универсальное представление для получения URL редиректа."""

    permission_classes = (AllowAny,)

    def get(
        self,
        request: HttpRequest,
        provider: str,
        *_args: Any,
        **_kwargs: Any,
    ) -> Response:
        """Обрабатывает GET-запрос и возвращает сгенерированный URL."""
        logger.info(
            'Получен запрос на генерацию URL авторизации. Провайдер: %s',
            provider,
        )

        auth_url: str = social_auth_url_service.get_auth_url(
            provider_name=provider,
            request=request,
        )
        return Response(
            {'authorization_url': auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Авторизация через OAuth2 (Сценарий редиректа на бэкенд)',
        parameters=[
            OpenApiParameter(
                name='provider',
                type=str,
                location=OpenApiParameter.PATH,
                description=(
                    'Идентификатор OAuth2-провайдера '
                    '(значения: google, yandex, mailru)'
                ),
                required=True,
            ),
            SocialAuthQueryParamsSerializer,
        ],
        responses={
            302: SOCIAL_LOGIN_REDIRECT_SCHEMA,
            400: SOCIAL_LOGIN_ERROR_SCHEMA,
        },
    ),
    post=extend_schema(
        tags=['social_auth'],
        summary='Авторизация через OAuth2 (Сценарий обмена на фронтенде)',
        description=POST_SCENARIO_DESCRIPTION,
        parameters=[
            OpenApiParameter(
                name='provider',
                type=str,
                location=OpenApiParameter.PATH,
                description=(
                    'Идентификатор OAuth2-провайдера '
                    '(значения: google, yandex, mailru)'
                ),
                required=True,
            ),
        ],
        request=SocialAuthCodeRequestSerializer,
        responses={
            200: SocialLoginSuccessResponseSerializer,
            400: SOCIAL_LOGIN_ERROR_SCHEMA,
        },
    ),
)
class SocialAuthCallbackView(SocialAuthCallbackMixin, SocialLoginView):
    """Универсальное параметризованное представление для callback OAuth2.

    Раздел технического долга:
    TODO: Разработать и внедрить сквозную верификацию параметра `state`
    для всех поддерживаемых провайдеров (Google, Yandex, Mail.ru)
    с целью обеспечения полноценной защиты от CSRF-атак.
    Необходимо интегрировать генерацию криптографического токена
    на этапе создания ссылок (в SocialAuthUrlService) с сохранением
    в сессию или подписанные куки пользователя, и последующую
    автоматическую или ручную проверку в методе dispatch/get.
    """

    permission_classes = (AllowAny,)
    client_class: type[OAuth2Client] = OAuth2Client
    serializer_class: type[
        SafeSocialLoginSerializer
    ] = SafeSocialLoginSerializer

    # Декларируем атрибуты на уровне класса для динамической подстановки
    # параметров провайдера
    adapter_class: type | None = None
    callback_url: str = ''

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        """Динамически настраивает параметры провайдера для инстанса."""
        provider_name: str = kwargs.get('provider', '')
        self.provider_key = provider_name.lower()

        # Получаем конфигурацию провайдера из чистой функции сервисного слоя
        adapter_class, callback_url = get_provider_config(provider_name)

        # Динамически переопределяем свойства инстанса для текущего запроса
        self.adapter_class = adapter_class
        self.callback_url = callback_url

        return super().dispatch(request, *args, **kwargs)
