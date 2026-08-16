import logging
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import (
    AuthenticationFailed,
    InvalidToken,
)

from users.models import User
from users.services.profile import update_last_login

logger = logging.getLogger(__name__)


class UpdateLastActivityMiddleware:
    """Middleware для обновления last_login активных пользователей.

    Обновляет last_login при каждом запросе от аутентифицированного
    пользователя.
    JWT-пользователь определяется путём парсинга access-токена из
    заголовка Authorization или куки access-token.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
    ) -> None:
        """Инициализирует middleware с функцией обработки запросов."""
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def _get_user_from_jwt(self, request: HttpRequest) -> User | None:
        """Попытаться извлечь пользователя из JWT-токена.

        Парсит access-токен из заголовка Authorization (Bearer) или
        из cookie.
        """
        # Пробуем заголовок Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            raw_token = auth_header.removeprefix('Bearer ')
            logger.debug(
                'JWT токен извлечён из заголовка Authorization: path=%s',
                request.path,
            )
        else:
            # Пробуем куку access-token
            raw_token = request.COOKIES.get(
                settings.REST_AUTH.get('JWT_AUTH_COOKIE', 'access-token'),
            )
            if raw_token:
                logger.debug(
                    'JWT токен извлечён из куки: path=%s',
                    request.path,
                )
        if not raw_token:
            logger.debug(
                'JWT токен не найден (ни заголовок, ни кука): path=%s',
                request.path,
            )
            return None
        try:
            token_bytes = str(raw_token).encode('utf-8')
            validated_token = self.jwt_auth.get_validated_token(
                token_bytes,
            )
            user: User = self.jwt_auth.get_user(validated_token)
            logger.debug(
                'Пользователь извлечён из JWT: user_id=%s, path=%s',
                getattr(user, 'pk', None),
                request.path,
            )
            return user
        except InvalidToken:
            logger.warning(
                'Невалидный JWT токен: path=%s',
                request.path,
            )
            return None
        except AuthenticationFailed:
            logger.warning(
                'Пользователь из JWT не найден в БД: path=%s',
                request.path,
            )
            return None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Обновляет last_login для аутентифицированных пользователей."""
        if request.user.is_authenticated and isinstance(request.user, User):
            logger.debug(
                'Обновление last_login для аутентифицированного '
                'пользователя: user_id=%s, path=%s',
                request.user.pk,
                request.path,
            )
            update_last_login(request.user)
        else:
            user = self._get_user_from_jwt(request)
            if user is not None:
                logger.debug(
                    'Обновление last_login для пользователя из JWT: '
                    'user_id=%s, path=%s',
                    user.pk,
                    request.path,
                )
                update_last_login(user)
        return self.get_response(request)
