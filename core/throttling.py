import logging
from typing import Any, Optional

from django.conf import settings
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)


class UniversalRateThrottle(SimpleRateThrottle):
    """Единый throttle-класс с разными скоупами для анонимов и авторизованных.

    Лимиты для анонимов и авторизованных настраивать через
    префиксы anon_ / user_.

    Пример настройки в settings.py:
        DEFAULT_THROTTLE_CLASSES = [
            'core.throttling.UniversalRateThrottle',
        ]
        DEFAULT_THROTTLE_RATES = {
            'anon_default': '50/min',
            'user_default': '500/min',
            'anon_login': '5/min',
            'user_login': '5/min',
        }
    """

    scope = 'default'

    def __init__(self) -> None:
        """Инициализируем SimpleRateThrottle, устанавливаем атрибуты."""
        super().__init__()

    def _get_scope_key(self, request: Request) -> str:
        """Определить ключ скоупа в зависимости от аутентификации."""
        if request.user and request.user.is_authenticated:
            return f'user_{self.scope}'
        return f'anon_{self.scope}'

    def _get_rate_for_scope(self, scope: str) -> Optional[str]:
        """Получить rate для указанного скоупа из настроек."""
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        return rates.get(scope)

    def get_rate(self) -> str:
        """Возвращает rate для парсинга в parse_rate().

        Поскольку на момент вызова get_rate() нет доступа к request,
        возвращаем rate для анонимов как fallback.
        """
        rate = self._get_rate_for_scope(f'anon_{self.scope}')
        if rate:
            return rate
        rate = self._get_rate_for_scope(f'user_{self.scope}')
        if rate:
            return rate
        raise ValueError(
            f'Не найден rate для скоупа "{self.scope}". '
            f'Укажите "anon_{self.scope}" или "user_{self.scope}" '
            f'в DEFAULT_THROTTLE_RATES.',
        )

    def allow_request(self, request: Request, view: Any) -> bool:
        """Проверяет, разрешён ли запрос в рамках текущего лимита.

        Логика:
            1. Определяет скоуп (anon_ / user_) на основе аутентификации.
            2. Получает лимит из настроек.
            3. Проверяет историю запросов в кэше.
            4. При превышении лимита возвращает False.
            5. При успехе обновляет кэш и возвращает True.

        Args:
            request: объект запроса DRF.
            view: объект вьюхи DRF.

        """
        scope_key = self._get_scope_key(request)
        rate = self._get_rate_for_scope(scope_key)
        if rate is None:
            logger.warning(
                'Не найден rate для скоупа "%s", троттлинг отключён.',
                scope_key,
            )
            return True
        self.num_requests, self.duration = self.parse_rate(rate)
        ident = request.user.pk if (
            request.user and request.user.is_authenticated
        ) else self.get_ident(request)
        cache_key = self.cache_format % {
            'scope': scope_key,
            'ident': ident,
        }
        history = self.cache.get(cache_key, [])
        now = self.timer()
        while history and history[-1] <= now - self.duration:
            history.pop()
        self.history = history
        self.now = now
        if len(history) >= self.num_requests:
            return False
        history.insert(0, now)
        self.cache.set(cache_key, history, timeout=self.duration)
        return True


class LoginRateThrottle(UniversalRateThrottle):
    """Троттлинг для эндпоинта логина."""

    scope = 'login'


class RegisterRateThrottle(UniversalRateThrottle):
    """Троттлинг для эндпоинта регистрации пользователя."""

    scope = 'register'


class PasswordResetRateThrottle(UniversalRateThrottle):
    """Троттлинг для эндпоинта сброса пароля."""

    scope = 'password_reset'


class PasswordChangeRateThrottle(UniversalRateThrottle):
    """Троттлинг для эндпоинта смены пароля."""

    scope = 'password_change'


class UploadFileRateThrottle(UniversalRateThrottle):
    """Троттлинг для эндпоинта загрузки медиа."""

    scope = 'upload'


class FeedbackRateThrottle(UniversalRateThrottle):
    """Троттлинг для создания обратной связи."""

    scope = 'feedback'
