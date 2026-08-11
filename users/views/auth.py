import logging
import os
from typing import Any, cast
from urllib.parse import unquote, urlencode, urljoin

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers import registry
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.mailru.views import MailRuOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.oauth2.views import OAuth2View
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponseRedirect
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
from users.models import User
from users.schemas import (
    SOCIAL_LOGIN_ERROR_SCHEMA,
    SOCIAL_LOGIN_REDIRECT_SCHEMA,
    SocialAuthQueryParamsSerializer,
)
from users.serializers.auth import (
    EmailChangeSerializer,
    SafeSocialLoginSerializer,
    SocialAuthUrlResponseSerializer,
)

UserModel = get_user_model()

logger = logging.getLogger(__name__)


class SocialAuthUrlView(APIView):
    """Базовый класс для генерации URL авторизации сторонних сервисов."""

    permission_classes = (AllowAny,)
    provider_id: str | None = None
    adapter_class: type | None = None

    def get(
        self,
        request: HttpRequest,
        *_args: Any,
        **_kwargs: Any,
    ) -> Response:
        """Обрабатывает GET-запрос и возвращает URL для авторизации."""
        logger.info(
            'Запуск генерации URL социальной авторизации. Провайдер: %s',
            self.provider_id,
        )
        adapter = get_adapter()
        app: SocialApp = adapter.get_app(request, provider=self.provider_id)

        provider: Any = registry.get_class(self.provider_id)(
            request,
            app=app,
        )

        # Создаем OAuth2View и привязываем к нему наш request и адаптер
        view: Any = OAuth2View()
        view.request = request

        if self.adapter_class is None:
            raise ValueError(
                f'Класс {self.__class__.__name__} обязан '
                f'определить свойство adapter_class.',
            )
        view.adapter = self.adapter_class(request)

        # Подменяем get_callback_url у view, чтобы пропустить NoReverseMatch
        callback_url: str = app.settings.get('CALLBACK_URL', '')
        view.get_callback_url = lambda _req, _app: callback_url

        # Получаем сконфигурированный клиент напрямую из allauth OAuth2View
        client: Any = getattr(view, 'get_client')(request, app)

        action = 'login'
        auth_params = provider.get_auth_params(request, action)
        state = provider.get_login_state(request, next_url=action)

        # Собираем финальную прямую ссылку на сервер провайдера
        auth_url: str = client.get_authorize_url(
            state=state,
            **auth_params,
        )

        logger.info(
            'Успешно сгенерирован URL авторизации для %s: %s',
            self.provider_id,
            auth_url,
        )

        return Response(
            {'authorization_url': auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Получить ссылку для авторизации через Google',
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class GoogleAuthUrlView(APIView):
    """Возвращает URL для редиректа на страницу авторизации Google."""

    permission_classes = (AllowAny,)

    def get(
        self,
        _request: HttpRequest,
        *_args: Any,
        **_kwargs: Any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Google."""
        logger.info('Запуск генерации URL авторизации Google.')

        config: dict[str, Any] = SOCIALACCOUNT_PROVIDERS['google']

        query_params: dict[str, str] = {
            'client_id': config['APP']['client_id'],
            'redirect_uri': config['CALLBACK_URL'],
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent',
        }

        base_url = 'https://accounts.google.com/o/oauth2/v2/auth'
        auth_url = f'{base_url}?{urlencode(query_params)}'

        logger.info(
            'Успешно сгенерирован URL авторизации Google. redirect_uri: %s',
            config['CALLBACK_URL'],
        )

        return Response(
            {'authorization_url': auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Получить ссылку для авторизации через Yandex',
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class YandexAuthUrlView(APIView):
    """Возвращает URL для редиректа на страницу авторизации Yandex."""

    permission_classes = (AllowAny,)

    def get(
        self,
        request: HttpRequest,
        *_args: Any,
        **_kwargs: Any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Yandex."""
        logger.info(
            'Запуск генерации URL авторизации Yandex. Переданный state: %s',
            request.GET.get('state', '<не передан>'),
        )

        config: dict[str, Any] = SOCIALACCOUNT_PROVIDERS['yandex']

        # Если фронтенд передает свой state для защиты или контекста
        state: str = request.GET.get('state', 'AAA')

        query_params: dict[str, str] = {
            'response_type': 'code',
            'client_id': config['APP']['client_id'],
            'redirect_uri': config['CALLBACK_URL'],
            'state': state,
        }

        base_url = 'https://oauth.yandex.ru/authorize'
        auth_url = f'{base_url}?{urlencode(query_params)}'

        logger.info(
            'Успешно сгенерирован URL авторизации Yandex. '
            'redirect_uri: %s, state: %s',
            config['CALLBACK_URL'],
            state,
        )

        return Response(
            {'authorization_url': auth_url},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Получить ссылку для авторизации через Mail.ru',
        responses={200: SocialAuthUrlResponseSerializer},
    ),
)
class MailRuAuthUrlView(APIView):
    """Возвращает URL для редиректа на страницу авторизации Mail.ru."""

    permission_classes = (AllowAny,)

    def get(
        self,
        _request: HttpRequest,
        *_args: Any,
        **_kwargs: Any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Mail.ru."""
        logger.info('Запуск генерации URL авторизации Mail.ru.')

        config: dict[str, Any] = SOCIALACCOUNT_PROVIDERS['mailru']

        query_params: dict[str, str] = {
            'client_id': config['APP']['client_id'],
            'response_type': 'code',
            'redirect_uri': config['CALLBACK_URL'],
        }

        base_url = 'https://connect.mail.ru/oauth/authorize'
        auth_url = f'{base_url}?{urlencode(query_params)}'

        logger.info(
            'Успешно сгенерирован URL авторизации Mail.ru. redirect_uri: %s',
            config['CALLBACK_URL'],
        )

        return Response(
            {'authorization_url': auth_url},
            status=status.HTTP_200_OK,
        )


# noinspection HttpUrlsUsage
class SocialLogin(SocialLoginView):
    """Базовый View для обработки запросов авторизации.

    Поддерживает получение кода через GET-запрос и последующий
    редирект пользователя на фронтенд с токенами в URL.
    """

    adapter_class: Any = None
    client_class: type[OAuth2Client] = OAuth2Client

    serializer_class: type[
        SafeSocialLoginSerializer
    ] = SafeSocialLoginSerializer

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirect:
        """Принимает код от провайдера через GET.

        Обменивает его на JWT и делает редирект.
        """
        provider_name: str = self.adapter_class.__name__.replace(
            'OAuth2Adapter',
            '',
        )
        logger.info(
            'Получен редирект (GET) от провайдера %s',
            provider_name,
        )

        raw_code: str = request.query_params.get('code', '')
        post_data = {'code': unquote(raw_code)}
        setattr(request, '_full_data', post_data)

        drf_response: Response = (
            self.post(request, *args, **kwargs) # type: ignore
        )

        access_token: str | None = drf_response.data.get('access')
        refresh_token: str | None = drf_response.data.get('refresh')

        frontend_host: str = os.getenv('HOST_URL', 'http://localhost:3000')
        if not frontend_host.startswith(('http://', 'https://')):
            frontend_host = f'https://{frontend_host}'
        base_frontend_url: str = urljoin(
            frontend_host,
            '/auth/callback',
        )

        query_params: dict[str, str | None] = {
            'access': access_token,
            'refresh': refresh_token,
        }
        redirect_url: str = (
            f'{base_frontend_url}?{urlencode(query_params)}'
        )

        redirect_response = HttpResponseRedirect(redirect_url)

        for (
            cookie_name,
            cookie_obj,
        ) in drf_response.cookies.items():
            redirect_response.set_cookie(
                key=cookie_name,
                value=cookie_obj.value,
                max_age=cookie_obj.get('max-age'),
                expires=cookie_obj.get('expires'),
                path=cookie_obj.get('path', '/'),
                domain=cookie_obj.get('domain'),
                secure=cookie_obj.get('secure', True),
                httponly=cookie_obj.get('httponly', True),
                samesite=cookie_obj.get('samesite', 'Lax'),
            )

        logger.info(
            'Пользователь перенаправлен на фронтенд с токенами',
        )
        return redirect_response

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Стандартный метод обмена кода на JWT."""
        provider_name: str = self.adapter_class.__name__.replace(
            'OAuth2Adapter',
            '',
        )
        data_dict = cast(dict[str, Any], request.data)
        if data_dict and 'code' in data_dict:
            raw_code: str = str(data_dict.get('code', ''))
            request.data['code'] = unquote(raw_code)

        # Возвращаем дефолтный вызов, так как сериализатор уже подменен
        response: Response = super().post(request, *args, **kwargs)

        logger.info(
            'Авторизация через %s аккаунт успешна',
            provider_name,
        )
        return response


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Вход через Yandex (Редирект от провайдера)',
        description=(
            'Принимает код авторизации от Yandex в URL-параметрах, '
            'создает/авторизует пользователя, устанавливает куки '
            'и редиректит на фронтенд (/auth/callback).'
        ),
        parameters=[SocialAuthQueryParamsSerializer],
        request=None,
        responses={
            302: SOCIAL_LOGIN_REDIRECT_SCHEMA,
            400: SOCIAL_LOGIN_ERROR_SCHEMA,
        },
    ),
)
class YandexLogin(SocialLogin):
    """View для обработки запросов авторизации через Yandex."""

    adapter_class: type[YandexOAuth2Adapter] = YandexOAuth2Adapter
    callback_url: str = SOCIALACCOUNT_PROVIDERS['yandex']['CALLBACK_URL']


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Вход через Google (Редирект от провайдера)',
        description=(
            'Принимает код авторизации от Google в URL-параметрах, '
            'создает/авторизует пользователя, устанавливает куки '
            'и редиректит на фронтенд (/auth/callback).'
        ),
        parameters=[SocialAuthQueryParamsSerializer],
        request=None,
        responses={
            302: SOCIAL_LOGIN_REDIRECT_SCHEMA,
            400: SOCIAL_LOGIN_ERROR_SCHEMA,
        },
    ),
)
class GoogleLogin(SocialLogin):
    """View для обработки запросов авторизации через Google."""

    adapter_class: type[GoogleOAuth2Adapter] = GoogleOAuth2Adapter
    callback_url: str = SOCIALACCOUNT_PROVIDERS['google']['CALLBACK_URL']


@extend_schema_view(
    get=extend_schema(
        tags=['social_auth'],
        summary='Вход через Mail.ru (Редирект от провайдера)',
        description=(
            'Принимает код авторизации от Mail.ru в URL-параметрах, '
            'создает/авторизует пользователя, устанавливает куки '
            'и редиректит на фронтенд (/auth/callback).'
        ),
        parameters=[SocialAuthQueryParamsSerializer],
        request=None,
        responses={
            302: SOCIAL_LOGIN_REDIRECT_SCHEMA,
            400: SOCIAL_LOGIN_ERROR_SCHEMA,
        },
    ),
)
class MailRuLogin(SocialLogin):
    """View для обработки запросов авторизации через Mail.ru."""

    adapter_class: type[MailRuOAuth2Adapter] = MailRuOAuth2Adapter
    callback_url: str = SOCIALACCOUNT_PROVIDERS['mailru']['CALLBACK_URL']


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
                    'detail': (
                        'Ссылка для подтверждения отправлена на новый email.'
                    ),
                },
                response_only=True,
            ),
        ],
    ),
)
class EmailChangeView(APIView):
    """View для инициации смены email авторизованным пользователем."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, *_args: Any, **_kwargs: Any) -> Response:
        """Обработать POST-запрос на изменение email пользователя."""
        user = cast(User, request.user)
        logger.info(
            'Запрос на изменение email пользователя. user_id=%s, old_email=%s',
            user.user_id,
            user.email,
        )
        serializer = EmailChangeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        new_email: str = serializer.validated_data['new_email']
        serializer.save()

        logger.info(
            'Отправлено письмо подтверждения на новый email. '
            'user_id=%s, old_email=%s, new_email=%s',
            user.user_id,
            user.email,
            new_email,
        )

        return Response(
            {
                'detail': 'Ссылка подтверждения отправлена на новый email.',
            },
            status=status.HTTP_200_OK,
        )
