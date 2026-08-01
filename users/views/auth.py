import logging
import os
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
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
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
from users.serializers.profile import MeProfileRetrieveSerializer

UserModel = get_user_model()

logger = logging.getLogger(__name__)


SOCIAL_LOGIN_SUCCESS_SERIALIZER: serializers.Serializer = inline_serializer(
    name='SocialLoginSuccessResponse',
    fields={
        'access': serializers.CharField(
            help_text='JWT access токен для аутентификации запросов.',
        ),
        'refresh': serializers.CharField(
            help_text='JWT refresh токен для обновления access токена.',
        ),
        'user': MeProfileRetrieveSerializer(),
        'access_expiration': serializers.DateTimeField(
            help_text='Дата и время истечения access токена.',
        ),
        'refresh_expiration': serializers.DateTimeField(
            help_text='Дата и время истечения refresh токена.',
        ),
    },
)

SOCIAL_LOGIN_ERROR_SERIALIZER: serializers.Serializer = inline_serializer(
    name='SocialLoginErrorResponse',
    fields={
        'non_field_errors': serializers.ListField(
            child=serializers.CharField(),
            default=[
                'Не удалось авторизоваться через социальную сеть. '
                'Неверный или истекший code.',
            ],
        ),
    },
)


class SocialAuthUrlView(APIView):
    """Базовый класс для генерации URL авторизации сторонних сервисов."""

    permission_classes = (AllowAny,)
    provider_id: str | None = None
    adapter_class: any = None

    def get(
        self,
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и возвращает URL для авторизации."""
        logger.info(
            'Запуск генерации URL социальной авторизации. Провайдер: %s',
            self.provider_id,
        )
        adapter = get_adapter()
        app: SocialApp = adapter.get_app(request, provider=self.provider_id)

        provider: Provider = registry.get_class(self.provider_id)(
            request,
            app=app,
        )

        # Создаем OAuth2View и привязываем к нему наш request и адаптер
        view = OAuth2View()
        view.request = request
        view.adapter = self.adapter_class(request)

        # Подменяем get_callback_url у view, чтобы пропустить NoReverseMatch
        callback_url: str = app.settings.get('CALLBACK_URL', '')
        view.get_callback_url = lambda req, app: callback_url

        # Получаем сконфигурированный клиент напрямую из allauth OAuth2View
        client = view.get_client(request, app)

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


class SocialLogin(SocialLoginView):
    """Базовый View для обработки запросов авторизации.

    Обрабатывает запросы авторизации через сторонние приложения.
    """

    client_class = OAuth2Client

    def post(
        self,
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Перехватывает запрос и очищает URL-кодированный code."""
        provider_name: str = self.adapter_class.__name__.replace(
            'OAuth2Adapter',
            '',
        )

        logger.info(
            'Запрос на авторизацию через %s аккаунт',
            provider_name,
        )

        if request.data and 'code' in request.data:
            raw_code: str = request.data.get('code', '')
            request.data['code'] = unquote(raw_code)

        response = super().post(request, *args, **kwargs)

        logger.info(
            'Авторизация через %s аккаунт успешна: user_id=%s',
            provider_name,
            request.user.user_id,
        )

        return response


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
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Google."""
        logger.info('Запуск генерации URL авторизации Google.')

        config: dict[str, any] = SOCIALACCOUNT_PROVIDERS['google']

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
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Google',
        description=(
            'Принимает код авторизации от Google и возвращает '
            'JWT-токены с данными профиля.'
        ),
        request=SocialAuthCodeRequestSerializer,
        responses={
            200: SOCIAL_LOGIN_SUCCESS_SERIALIZER,
            400: SOCIAL_LOGIN_ERROR_SERIALIZER,
        },
    ),
)
class GoogleLogin(SocialLogin):
    """View для обработки запросов авторизации через Google."""

    adapter_class = GoogleOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['google']['CALLBACK_URL']

    def post(
        self,
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Перехватывает запрос и очищает URL-кодированный code."""
        code: str | None = request.data.get('code') if request.data else None
        logger.info(
            'Запрос на авторизацию через Google. '
            'code (первые 20 символов): %s',
            code[:20] if code else None,
        )

        if code:
            request.data['code'] = unquote(code)
            logger.info(
                'Google: code декодирован из URL-encoding. '
                'Было: %s..., стало: %s...',
                code[:20],
                request.data['code'][:20],
            )

        response = super().post(request, *args, **kwargs)

        logger.info(
            'Google: авторизация успешна. user_id=%s, status=%s',
            request.user.user_id,
            response.status_code,
        )

        return response


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
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Yandex."""
        logger.info(
            'Запуск генерации URL авторизации Yandex. Переданный state: %s',
            request.GET.get('state', '<не передан>'),
        )

        config: dict[str, any] = SOCIALACCOUNT_PROVIDERS['yandex']

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
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Yandex',
        description=(
            'Принимает код авторизации от Yandex и возвращает '
            'JWT-токены с данными профиля.'
        ),
        request=SocialAuthCodeRequestSerializer,
        responses={
            200: SOCIAL_LOGIN_SUCCESS_SERIALIZER,
            400: SOCIAL_LOGIN_ERROR_SERIALIZER,
        },
    ),
)
class YandexLogin(SocialLogin):
    """View для обработки запросов авторизации через Yandex."""

    adapter_class = YandexOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['yandex']['CALLBACK_URL']

    def post(
        self,
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Перехватывает запрос и очищает URL-кодированный code."""
        code: str | None = request.data.get('code') if request.data else None
        logger.info(
            'Запрос на авторизацию через Yandex. '
            'code (первые 20 символов): %s',
            code[:20] if code else None,
        )

        if code:
            request.data['code'] = unquote(code)
            logger.info(
                'Yandex: code декодирован из URL-encoding. '
                'Было: %s..., стало: %s...',
                code[:20],
                request.data['code'][:20],
            )

        response = super().post(request, *args, **kwargs)

        logger.info(
            'Yandex: авторизация успешна. user_id=%s, status=%s',
            request.user.user_id,
            response.status_code,
        )

        return response


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
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Обрабатывает GET-запрос и формирует прямую ссылку для Mail.ru."""
        logger.info('Запуск генерации URL авторизации Mail.ru.')

        config: dict[str, any] = SOCIALACCOUNT_PROVIDERS['mailru']

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


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Mail.ru',
        description=(
            'Принимает код авторизации от Mail.ru и возвращает '
            'JWT-токены с данными профиля.'
        ),
        request=SocialAuthCodeRequestSerializer,
        responses={
            200: SOCIAL_LOGIN_SUCCESS_SERIALIZER,
            400: SOCIAL_LOGIN_ERROR_SERIALIZER,
        },
    ),
)
class MailRuLogin(SocialLogin):
    """View для обработки запросов авторизации через Mail.ru."""

    adapter_class = MailRuOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['mailru']['CALLBACK_URL']

    def post(
        self,
        request: HttpRequest,
        *args: any,
        **kwargs: any,
    ) -> Response:
        """Перехватывает запрос и очищает URL-кодированный code."""
        code: str | None = request.data.get('code') if request.data else None
        logger.info(
            'Запрос на авторизацию через Mail.ru. '
            'code (первые 20 символов): %s',
            code[:20] if code else None,
        )

        if code:
            request.data['code'] = unquote(code)
            logger.info(
                'Mail.ru: code декодирован из URL-encoding. '
                'Было: %s..., стало: %s...',
                code[:20],
                request.data['code'][:20],
            )

        response = super().post(request, *args, **kwargs)

        logger.info(
            'Mail.ru: авторизация успешна. user_id=%s, status=%s',
            request.user.user_id,
            response.status_code,
        )

        return response


class SocialCallbackView(APIView):
    """Базовый GET-эндпоинт для OAuth callback от провайдера.

    Провайдер редиректит браузер пользователя на этот URL после авторизации.
    View обменивает code на токены и редиректит на фронтенд с JWT.
    """

    permission_classes = (AllowAny,)
    provider_name: str = ''
    login_view_class: type[SocialLogin] | None = None
    api_path: str = ''

    def get(self, request: HttpRequest, *args: any, **kwargs: any) -> Response:
        """Принять code от провайдера, авторизовать и редиректить."""
        code: str = request.GET.get('code', '')
        if not code:
            logger.warning('%s callback: code не передан', self.provider_name)
            return Response(
                {'error': 'code is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            '%s callback: получен code (первые 20 символов): %s',
            self.provider_name,
            code[:20],
        )

        # Создаём POST-запрос программно и передаём в SocialLogin
        from django.test.client import RequestFactory

        factory = RequestFactory()
        post_request = factory.post(
            self.api_path,
            {'code': code},
            format='json',
        )
        post_request.user = request.user
        post_request.session = request.session

        # Копируем атрибуты из оригинального запроса
        post_request.META = request.META.copy()
        post_request.META['CONTENT_TYPE'] = 'application/json'

        # Вызываем LoginView
        login_view = self.login_view_class.as_view()
        response = login_view(post_request)

        if response.status_code != 200:
            logger.error(
                '%s callback: ошибка авторизации. status=%s, data=%s',
                self.provider_name,
                response.status_code,
                response.data,
            )
            host_url = os.getenv('HOST_URL', 'http://localhost:3000')
            redirect_url = (
                f'{host_url}/auth/callback?error='
                f'Не+удалось+авторизоваться+через+{self.provider_name}'
            )
            return redirect(redirect_url)

        # Извлекаем токены из ответа
        data = response.data
        access_token = data.get('access', '')
        refresh_token = data.get('refresh', '')
        user_id = data.get('user', {}).get('user_id', '')

        host_url = os.getenv('HOST_URL', 'http://localhost:3000')
        redirect_url = (
            f'{host_url}/auth/callback'
            f'?access={access_token}'
            f'&refresh={refresh_token}'
            f'&user_id={user_id}'
        )

        logger.info(
            '%s callback: успех, редирект на фронтенд. user_id=%s',
            self.provider_name,
            user_id,
        )

        return redirect(redirect_url)


class YandexCallbackView(SocialCallbackView):
    """GET-эндпоинт для OAuth callback от Yandex."""

    provider_name = 'Yandex'
    login_view_class = YandexLogin
    api_path = '/api/v1/user/auth/yandex/'


class GoogleCallbackView(SocialCallbackView):
    """GET-эндпоинт для OAuth callback от Google."""

    provider_name = 'Google'
    login_view_class = GoogleLogin
    api_path = '/api/v1/user/auth/google/'


class MailRuCallbackView(SocialCallbackView):
    """GET-эндпоинт для OAuth callback от Mail.ru."""

    provider_name = 'Mail.ru'
    login_view_class = MailRuLogin
    api_path = '/api/v1/user/auth/mailru/'


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

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Обработать POST-запрос на изменение email пользователя."""
        logger.info(
            'Запрос на изменение email пользователя. user_id=%s, old_email=%s',
            request.user.user_id,
            request.user.email,
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
            request.user.user_id,
            request.user.email,
            new_email,
        )

        return Response(
            {
                'detail': 'Ссылка подтверждения отправлена на новый email.',
            },
            status=status.HTTP_200_OK,
        )


# class YandexCallbackView(APIView):
#     """Обрабатывает callback от Яндекса после авторизации пользователя.

#     Яндекс редиректит сюда с code и state после успешной авторизации.
#     View перенаправляет пользователя на фронтенд, который отправляет
#     POST запрос с code на /api/v1/user/auth/yandex/ для получения JWT.
#     """

#     permission_classes = (AllowAny,)

#     def get(
#         self,
#         request: HttpRequest,
#         *args: Any,
#         **kwargs: Any,
#     ) -> HttpResponseRedirect:
#         """Обрабатывает GET-редирект от Яндекса с authorization code."""
#         code: str = request.GET.get('code', '')
#         state: str = request.GET.get('state', 'AAA')

#         logger.info(
#             'Yandex callback получен. code (первые 20 символов): %s, '
#             'state: %s',
#             code[:20] if code else None,
#             state,
#         )

#         if not code:
#             logger.error('Yandex callback: code не получен от Яндекса.')
#             host_url = os.getenv('HOST_URL', 'http://localhost:3000')
#             error_url = f'{host_url}/auth/yandex/callback?error=no_code'
#             return HttpResponseRedirect(error_url)

#         # Декодируем code из URL-encoding
#         code = unquote(code)

#         # Редиректим пользователя на фронтенд, который сам отправит
#         # POST запрос с code на /api/v1/user/auth/yandex/
#         host_url = os.getenv('HOST_URL', 'http://localhost:3000')
#         redirect_url = (
#             f'{host_url}/auth/yandex/callback'
#             f'?code={code}&state={state}'
#         )

#         logger.info(
#             'Yandex callback: редирект на фронтенд. redirect_url: %s',
#             redirect_url,
#         )

#         return HttpResponseRedirect(redirect_url)
