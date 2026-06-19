from typing import Callable

from django.http import HttpRequest, HttpResponse

from users.services import update_last_login


class UpdateLastActivityMiddleware:
    """Middleware для обновления last_login активных пользователей.

    Обновляет last_login при каждом запросе от аутентифицированного
    пользователя.

    Используется в проектах, для отслеживания оактивности автора проекта.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
    ) -> None:
        """Инициализирует middleware с функцией обработки запросов."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Обновляет last_login для аутентифицированных пользователей."""
        if request.user.is_authenticated:
            update_last_login(request.user)
        return self.get_response(request)
