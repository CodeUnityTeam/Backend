from typing import Any
from urllib.parse import unquote, urlencode

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers import registry
from allauth.socialaccount.providers.base import Provider
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.mailru.views import MailRuOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.oauth2.views import OAuth2View
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.settings import SOCIALACCOUNT_PROVIDERS
from users.serializers.auth import (
    EmailChangeSerializer,
    SocialAuthCodeRequestSerializer,
    SocialAuthUrlResponseSerializer,
)

UserModel = get_user_model()


# TODO [USERS-2/15]: Заменить ручное построение OAuth URL на стандартный allauth OAuth2View.
#   Проблема: GoogleAuthUrlView (строка 118), YandexAuthUrlView (строка 168),
#   MailRuAuthUrlView (строка 219) вручную собирают URL через urlencode:
#     query_params = {"client_id": ..., "redirect_uri": ...}
#     auth_url = f"{base_url}?{urlencode(query_params)}"
#   Это дублирование кода, риск рассинхронизации параметров и игнорирование
#   стандартного механизма allauth.
#
#   Решение через стандартный DRF + allauth:
#   Удалить три конкретные вьюхи и использовать единый SocialAuthUrlView
#   с параметром provider_id в URL:
#
#   class SocialAuthUrlView(APIView):
#       """Единый View для получения OAuth URL через allauth."""
#       permission_classes = [AllowAny]
#
#       def get(self, request, provider_id=None):
#           adapter = get_adapter()
#           provider_map = {
#               'google': GoogleOAuth2Adapter,
#               'yandex': YandexOAuth2Adapter,
#               'mailru': MailRuOAuth2Adapter,
#           }
#           adapter_class = provider_map.get(provider_id)
#           if not adapter_class:
#               return Response(
#                   {'error': 'Unknown provider'},
#                   status=status.HTTP_400_BAD_REQUEST,
#               )
#
#           app = adapter.get_app(request, provider=provider_id)
#           provider = registry.get_class(provider_id)(request, app=app)
#           view = OAuth2View()
#           view.request = request
#           view.adapter = adapter_class(request)
#           callback_url = SOCIALACCOUNT_PROVIDERS[provider_id]['CALLBACK_URL']
#           view.get_callback_url = lambda req, app: callback_url
#           client = view.get_client(request, app)
#           auth_params = provider.get_auth_params(request, 'login')
#           state = provider.get_login_state(request, next_url='login')
#           auth_url = client.get_authorize_url(state=state, **auth_params)
#
#           return Response({'authorization_url': auth_url})
#
#   URL-ы в urls.py:
#     path('social/<str:provider_id>/url/', SocialAuthUrlView.as_view()),
class SocialAuthUrlView(APIView):
    """Базовый класс для генерации URL авторизации сторонних сервисов."""

    permission_classes = [AllowAny]
    provider_id: str | None = None
    adapter_class: any = None

    def get(
        self, request: HttpRequest, *args: any, **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и возвращает URL для авторизации."""
        adapter = get_adapter()
        app: SocialApp = adapter.get_app(request, provider=self.provider_id)

        provider: Provider = registry.get_class(self.provider_id)(
            request, app=app,
        )

        # Создаем OAuth2View и привязываем к нему наш request и адаптер
        view = OAuth2View()
        view.request = request
        view.adapter = self.adapter_class(request)

        # Подменяем get_callback_url у view, чтобы пропустить NoReverseMatch
        callback_url: str = app.settings.get("CALLBACK_URL", "")
        view.get_callback_url = lambda req, app: callback_url

        # Получаем сконфигурированный клиент напрямую из allauth OAuth2View
        client = view.get_client(request, app)

        action = "login"
        auth_params = provider.get_auth_params(request, action)
        state = provider.get_login_state(request, next_url=action)

        # Собираем финальную прямую ссылку на сервер провайдера
        auth_url: str = client.get_authorize_url(
            state=state,
            **auth_params,
        )

        return Response(
            {"authorization_url": auth_url},
            status=status.HTTP_200_OK,
        )


class SocialLogin(SocialLoginView):
    """Базовый View для обработки запросов авторизации.

    Обрабатывает запросы авторизации через сторонние приложения.
    """

    client_class = OAuth2Client

    def post(
        self, request: HttpRequest, *args: any, **kwargs: any,
    ) -> Response:
        """Перехватывает запрос и очищает URL-кодированный code."""
        if request.data and "code" in request.data:
            # Извлекаем сырой код, очищаем его и записываем обратно
            raw_code: str = request.data.get("code", "")
            request.data["code"] = unquote(raw_code)

        return super().post(request, *args, **kwargs)


# TODO [USERS-2/15]: Заменить ручное построение OAuth URL на стандартный allauth OAuth2View.
#   Проблема: GoogleAuthUrlView (строка 118), YandexAuthUrlView (строка 168),
#   MailRuAuthUrlView (строка 219) вручную собирают URL через urlencode:
#     query_params = {"client_id": ..., "redirect_uri": ...}
#     auth_url = f"{base_url}?{urlencode(query_params)}"
#   Это дублирование кода, риск рассинхронизации параметров и игнорирование
#   стандартного механизма allauth.
#
#   Решение через стандартный DRF + allauth:
#   Удалить три конкретные вьюхи и использовать единый SocialAuthUrlView
#   с параметром provider_id в URL:
#
#   class SocialAuthUrlView(APIView):
#       """Единый View для получения OAuth URL через allauth."""
#       permission_classes = [AllowAny]
#
#       def get(self, request, provider_id=None):
#           adapter = get_adapter()
#           provider_map = {
#               'google': GoogleOAuth2Adapter,
#               'yandex': YandexOAuth2Adapter,
#               'mailru': MailRuOAuth2Adapter,
#           }
#           adapter_class = provider_map.get(provider_id)
#           if not adapter_class:
#               return Response(
#                   {'error': 'Unknown provider'},
#                   status=status.HTTP_400_BAD_REQUEST,
#               )
#
#           app = adapter.get_app(request, provider=provider_id)
#           provider = registry.get_class(provider_id)(request, app=app)
#           view = OAuth2View()
#           view.request = request
#           view.adapter = adapter_class(request)
#           callback_url = SOCIALACCOUNT_PROVIDERS[provider_id]['CALLBACK_URL']
#           view.get_callback_url = lambda req, app: callback_url
#           client = view.get_client(request, app)
#           auth_params = provider.get_auth_params(request, 'login')
#           state = provider.get_login_state(request, next_url='login')
#           auth_url = client.get_authorize_url(state=state, **auth_params)
#
#           return Response({'authorization_url': auth_url})
#
#   URL-ы в urls.py:
#     path('social/<str:provider_id>/url/', SocialAuthUrlView.as_view()),


@extend_schema_view(
    post=extend_schema(
        tags=['profile'],
        summary='Запрос на изменение email авторизованным пользователем',
        description='Запрос на смену email и отправку письма подтверждения.',
        request=EmailChangeSerializer,
        responses={
            200: inline_serializer(
                name='EmailChangeSuccessResponse',
                fields={
                    'detail': serializers.CharField(
                        help_text=(
                            'Сообщение об успешной отправке ссылки '
                            'подтверждения.'
                        ),
                    ),
                },
            ),
        },
        examples=[
            OpenApiExample(
                name='Успешный запрос',
                value={
                    "detail": (
                        "Ссылка для подтверждения отправлена на новый email."
                    ),
                },
                response_only=True,
            ),
        ],
    ),
)
class EmailChangeView(APIView):
    """View для инициации смены email авторизованным пользователем."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Обработать POST-запрос на изменение email пользователя."""
        serializer = EmailChangeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'detail': 'Ссылка подтверждения отправлена на новый email.',
            },
            status=status.HTTP_200_OK,
        )
