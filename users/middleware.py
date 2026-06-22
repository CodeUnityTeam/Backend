from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from users.services import update_last_login


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

    def _get_user_from_jwt(self, request: HttpRequest) -> object | None:
        """Попытаться извлечь пользователя из JWT-токена.

        Парсит access-токен из заголовка Authorization (Bearer) или
        из куки access-token.
        """
        # Пробуем заголовок Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            raw_token = auth_header.removeprefix('Bearer ')
        else:
            # Пробуем куку access-token
            raw_token = request.COOKIES.get(
                settings.REST_AUTH.get('JWT_AUTH_COOKIE', 'access-token'),
            )
        if not raw_token:
            return None
        try:
            validated_token = self.jwt_auth.get_validated_token(raw_token)
            return self.jwt_auth.get_user(validated_token)
        except InvalidToken:
            return None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Обновляет last_login для аутентифицированных пользователей."""
        if request.user.is_authenticated:
            update_last_login(request.user)
        else:
            user = self._get_user_from_jwt(request)
            if user is not None:
                update_last_login(user)
        return self.get_response(request)
