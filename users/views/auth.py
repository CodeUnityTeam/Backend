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


@extend_schema_view(
    get=extend_schema(
        tags=["social_auth"],
        summary="Получить ссылку для авторизации через Google",
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class GoogleAuthUrlView(APIView):
    """Возвращает URL для редиректа на страницу авторизации Google."""

    permission_classes = [AllowAny]

    def get(
        self, request: HttpRequest, *args: any, **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Google."""
        config: dict[str, any] = SOCIALACCOUNT_PROVIDERS["google"]

        query_params: dict[str, str] = {
            "client_id": config["APP"]["client_id"],
            "redirect_uri": config["CALLBACK_URL"],
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }

        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        auth_url = f"{base_url}?{urlencode(query_params)}"

        return Response(
            {"authorization_url": auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Google',
        request=SocialAuthCodeRequestSerializer,
    ),
)
class GoogleLogin(SocialLogin):
    """View для обработки запросов авторизации через Google."""

    adapter_class = GoogleOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['google']['CALLBACK_URL']


@extend_schema_view(
    get=extend_schema(
        tags=["social_auth"],
        summary="Получить ссылку для авторизации через Yandex",
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class YandexAuthUrlView(APIView):
    """Возвращает URL для редиректа на страницу авторизации Yandex."""

    permission_classes = [AllowAny]

    def get(
        self, request: HttpRequest, *args: any, **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Yandex."""
        config: dict[str, any] = SOCIALACCOUNT_PROVIDERS["yandex"]

        # Если фронтенд передает свой state для защиты или контекста
        state: str = request.GET.get("state", "AAA")

        query_params: dict[str, str] = {
            "response_type": "code",
            "client_id": config["APP"]["client_id"],
            "redirect_uri": config["CALLBACK_URL"],
            "state": state,
        }

        base_url = "https://oauth.yandex.ru/authorize"
        auth_url = f"{base_url}?{urlencode(query_params)}"

        return Response(
            {"authorization_url": auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Yandex',
        request=SocialAuthCodeRequestSerializer,
    ),
)
class YandexLogin(SocialLogin):
    """View для обработки запросов авторизации через Yandex."""

    adapter_class = YandexOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['yandex']['CALLBACK_URL']


@extend_schema_view(
    get=extend_schema(
        tags=["social_auth"],
        summary="Получить ссылку для авторизации через Mail.ru",
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class MailRuAuthUrlView(APIView):
    """Возвращает URL для редиректа на страницу авторизации Mail.ru."""

    permission_classes = [AllowAny]

    def get(
        self, request: HttpRequest, *args: any, **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Mail.ru."""
        config: dict[str, any] = SOCIALACCOUNT_PROVIDERS["mailru"]

        query_params: dict[str, str] = {
            "client_id": config["APP"]["client_id"],
            "response_type": "code",
            "redirect_uri": config["CALLBACK_URL"],
        }

        base_url = "https://connect.mail.ru/oauth/authorize"
        auth_url = f"{base_url}?{urlencode(query_params)}"

        return Response(
            {"authorization_url": auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Mail.ru',
        request=SocialAuthCodeRequestSerializer,
    ),
)
class MailRuLogin(SocialLogin):
    """View для обработки запросов авторизации через Mail.ru."""

    adapter_class = MailRuOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['mailru']['CALLBACK_URL']


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
