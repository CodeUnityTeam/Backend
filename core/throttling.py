import logging
from typing import Optional

from django.conf import settings
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

    def __init__(self):
        # SimpleRateThrottle.__init__ вызывает get_rate() и parse_rate().
        # Нам это не нужно, т.к. rate будет определён в allow_request.
        # Просто инициализируем родительский SimpleRateThrottle,
        # который в __init__ ничего не делает кроме установки атрибутов.
        super(SimpleRateThrottle, self).__init__()

    def _get_scope_key(self, request) -> str:
        """Определить ключ скоупа в зависимости от аутентификации."""
        if request.user and request.user.is_authenticated:
            return f'user_{self.scope}'
        return f'anon_{self.scope}'

    def _get_rate_for_scope(self, scope: str) -> Optional[str]:
        """Получить rate для указанного скоупа из настроек."""
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        return rates.get(scope)

    def get_rate(self):
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
            f'в DEFAULT_THROTTLE_RATES.'
        )

    def allow_request(self, request, view):
        """Проверяем лимит для соответствующего скоупа (anon/user)."""
        scope_key = self._get_scope_key(request)
        rate = self._get_rate_for_scope(scope_key)
        if rate is None:
            logger.warning(
                'Не найден rate для скоупа "%s", троттлинг отключён.',
                scope_key,
            )
            return True

        self.num_requests, self.duration = self.parse_rate(rate)

        # Определяем идентификатор для ключа кэша
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        cache_key = self.cache_format % {
            'scope': scope_key,
            'ident': ident,
        }

        # Проверяем лимит через историю запросов в кэше
        history = self.cache.get(cache_key, [])
        now = self.timer()

        # Отфильтровываем устаревшие записи
        while history and history[-1] <= now - self.duration:
            history.pop()

        if len(history) >= self.num_requests:
            return self.throttle_failure()

        return self.throttle_success(cache_key)


class LoginRateThrottle(UniversalRateThrottle):
    scope = 'login'


class RegisterRateThrottle(UniversalRateThrottle):
    scope = 'register'


class PasswordResetRateThrottle(UniversalRateThrottle):
    scope = 'password_reset'


class PasswordChangeRateThrottle(UniversalRateThrottle):
    scope = 'password_change'
