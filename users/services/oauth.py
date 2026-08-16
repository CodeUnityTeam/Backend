import logging
import os
from typing import Any, cast
from urllib.parse import unquote, urlencode, urljoin

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.mailru.views import MailRuOAuth2Adapter
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# =============================================================================
# ЕДИНАЯ КАРТА КОНФИГУРАЦИИ OAUTH PROVIDERS
# =============================================================================
OAUTH_PROVIDERS_MAP: dict[str, dict[str, Any]] = {
    'google': {
        'adapter_class': GoogleOAuth2Adapter,
        'builder_method': '_get_google_url',
    },
    'yandex': {
        'adapter_class': YandexOAuth2Adapter,
        'builder_method': '_get_yandex_url',
    },
    'mailru': {
        'adapter_class': MailRuOAuth2Adapter,
        'builder_method': '_get_mailru_url',
    },
}


class SocialAuthUrlService:
    """Сервис для генерации URL авторизации сторонних провайдеров."""

    def get_auth_url(self, provider_name: str, request: HttpRequest) -> str:
        """Диспетчер, возвращающий готовый URL для указанного провайдера."""
        provider_key: str = provider_name.lower()
        provider_info: dict[str, Any] | None = OAUTH_PROVIDERS_MAP.get(
            provider_key,
        )

        if not provider_info:
            logger.warning(
                'Попытка запроса неподдерживаемого провайдера: %s',
                provider_name,
            )
            raise ValidationError({
                'detail': f"Провайдер '{provider_name}' не поддерживается.",
            })

        # Динамически находим и вызываем приватный метод сборки по его имени
        method_name: str = provider_info['builder_method']
        builder_method = getattr(self, method_name, None)

        if not builder_method:
            logger.error(
                'Метод сборки %s не реализован в классе.',
                method_name,
            )
            raise ValidationError({
                'detail': 'Внутренняя ошибка конфигурации сервиса.',
            })

        providers_config: dict[str, Any] = getattr(
            settings,
            'SOCIALACCOUNT_PROVIDERS',
            {},
        )
        config: dict[str, Any] | None = providers_config.get(provider_key)

        if not config or 'APP' not in config:
            logger.error(
                'Конфигурация для провайдера %s отсутствует в settings.py',
                provider_name,
            )
            raise ValidationError(
                {
                    'detail': (
                        f"Провайдер '{provider_name}' "
                        f'не настроен на сервере.'
                    ),
                },
            )
        # noinspection PyCallingNonCallable
        return builder_method(config, request)  # type: ignore[operator]

    def _get_google_url(
        self,
        config: dict[str, Any],
        _request: HttpRequest,
    ) -> str:
        """Формирует строку параметров и базовый URL для Google."""
        logger.info('Запуск генерации URL авторизации Google.')
        query_params: dict[str, str] = {
            'client_id': config['APP']['client_id'],
            'redirect_uri': config['CALLBACK_URL'],
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent',
        }
        base_url: str = 'https://accounts.google.com/o/oauth2/v2/auth'
        return f'{base_url}?{urlencode(query_params)}'

    def _get_yandex_url(
        self,
        config: dict[str, Any],
        request: HttpRequest,
    ) -> str:
        """Формирует строку параметров и базовый URL для Yandex."""
        state: str = request.GET.get('state', 'AAA')
        logger.info(
            'Запуск генерации URL авторизации Yandex. State: %s',
            state,
        )
        query_params: dict[str, str] = {
            'response_type': 'code',
            'client_id': config['APP']['client_id'],
            'redirect_uri': config['CALLBACK_URL'],
            'state': state,
        }
        base_url: str = 'https://oauth.yandex.ru/authorize'
        return f'{base_url}?{urlencode(query_params)}'

    def _get_mailru_url(
        self,
        config: dict[str, Any],
        _request: HttpRequest,
    ) -> str:
        """Формирует строку параметров и базовый URL для Mail.ru."""
        logger.info('Запуск генерации URL авторизации Mail.ru.')
        query_params: dict[str, str] = {
            'client_id': config['APP']['client_id'],
            'response_type': 'code',
            'redirect_uri': config['CALLBACK_URL'],
        }
        base_url: str = 'https://connect.mail.ru/oauth/authorize'
        return f'{base_url}?{urlencode(query_params)}'


social_auth_url_service = SocialAuthUrlService()


# noinspection HttpUrlsUsage
class SocialAuthCallbackMixin:
    """Миксин для обработки GET и POST сценариев социальной авторизации."""

    provider_key: str = ''

    def get(
            self,
            request: Request,
            *_args: Any,
            **_kwargs: Any,
    ) -> HttpResponseRedirect:
        """Второй сценарий (GET): Обработка редиректа от провайдера."""
        logger.info(
            'Старт обработки GET-редиректа для провайдера: %s',
            self.provider_key,
        )

        raw_code: str = request.query_params.get('code', '')
        if not raw_code:
            raise ValidationError({'code': 'Параметр code обязателен.'})

        # Помещаем декодированный код в request.data для штатной работы DRF
        request.data['code'] = unquote(raw_code)

        # Вызываем базовый метод post родительского класса SocialLoginView
        drf_response: Response = super().post(request)  # type: ignore[misc]

        access_token: str = drf_response.data.get('access', '')
        refresh_token: str = drf_response.data.get('refresh', '')

        frontend_host: str = os.getenv('HOST_URL', 'http://localhost:3000')
        if not frontend_host.startswith(('http://', 'https://')):
            frontend_host = f'https://{frontend_host}'

        base_frontend_url: str = urljoin(frontend_host, '/auth/callback')
        query_params: dict[str, str] = {
            'access': access_token,
            'refresh': refresh_token,
        }
        redirect_url: str = f'{base_frontend_url}?{urlencode(query_params)}'
        redirect_response: HttpResponseRedirect = HttpResponseRedirect(
            redirect_url,
        )

        # Переносим авторизационные куки, созданные dj-rest-auth
        for cookie_name, cookie_obj in drf_response.cookies.items():
            redirect_response.set_cookie(
                key=cookie_name,
                value=cookie_obj.value,
                max_age=cookie_obj.get('max-age'),
                expires=cookie_obj.get('expires'),
                path=cookie_obj.get('path', '/'),
                domain=cookie_obj.get('domain'),
                secure=cookie_obj.get('secure', False),
                httponly=cookie_obj.get('httponly', False),
                samesite=cookie_obj.get('samesite', 'Lax'),
            )

        logger.info(
            'GET-авторизация завершена для %s. '
            'Пользователь направлен на фронтенд.',
            self.provider_key,
        )
        return redirect_response

    def post(self, request: Request, *_args: Any, **_kwargs: Any) -> Response:
        """Первый сценарий (POST): Обмен кода силами фронтенда."""
        logger.info(
            'Старт POST-обмена кода для провайдера: %s',
            self.provider_key,
        )

        data_dict = cast(dict[str, Any], request.data)
        if data_dict and 'code' in data_dict:
            raw_code: str = str(data_dict.get('code', ''))
            request.data['code'] = unquote(raw_code)

        # Вызываем базовый метод post родительского класса SocialLoginView
        drf_response: Response = super().post(request)  # type: ignore[misc]

        user: Any = getattr(request, 'user', None)
        user_id: Any = getattr(user, 'user_id', 'анонимный_id')

        logger.info(
            'POST-авторизация успешна для %s. User ID: %s, Status: %s',
            self.provider_key,
            user_id,
            drf_response.status_code,
        )
        return drf_response


def get_provider_config(provider_name: str) -> tuple[type, str]:
    """Возвращает класс адаптера и callback_url для указанного провайдера."""
    provider_key: str = provider_name.lower()
    provider_info: dict[str, Any] | None = OAUTH_PROVIDERS_MAP.get(
        provider_key,
    )

    if not provider_info:
        logger.warning(
            'Запрошен неподдерживаемый провайдер: %s',
            provider_name,
        )
        raise ValidationError(
            {'detail': f"Провайдер '{provider_name}' не поддерживается."},
        )

    providers_config: dict[str, Any] = getattr(
        settings,
        'SOCIALACCOUNT_PROVIDERS',
        {},
    )
    config: dict[str, Any] = providers_config.get(provider_key, {})
    callback_url: str = config.get('CALLBACK_URL', '')

    return provider_info['adapter_class'], callback_url
