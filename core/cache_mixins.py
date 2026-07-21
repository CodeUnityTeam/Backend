import logging
from typing import Any

from django.core.cache import cache
from django.db.models import Count, QuerySet
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# =============================================================================
# Счётчики в Redis (incr/decr)
# =============================================================================


def _ck(prefix: str, object_id: str) -> str:
    """Сформировать ключ Redis для счётчика."""
    return f'{prefix}:{object_id}'


def incr_counter(prefix: str, object_id: str, delta: int = 1) -> int:
    """Увеличить счётчик. Если ключа нет — создать со значением delta."""
    key = _ck(prefix, object_id)
    try:
        new_value = cache.incr(key, delta)
        logger.debug('Счётчик увеличен: key=%s, delta=%d, new_value=%d', key, delta, new_value)
        return new_value
    except ValueError:
        cache.set(key, delta)
        logger.debug('Счётчик создан: key=%s, initial_value=%d', key, delta)
        return delta


def decr_counter(prefix: str, object_id: str, delta: int = 1) -> int:
    """Уменьшить счётчик. Не даёт уйти в минус."""
    key = _ck(prefix, object_id)
    try:
        new_value = cache.decr(key, delta)
        if new_value < 0:
            cache.set(key, 0)
            logger.debug('Счётчик обнулён (попытка уйти в минус): key=%s', key)
            return 0
        logger.debug('Счётчик уменьшен: key=%s, delta=%d, new_value=%d', key, delta, new_value)
        return new_value
    except ValueError:
        cache.set(key, 0)
        logger.debug('Счётчик создан с 0: key=%s', key)
        return 0


def get_counter(prefix: str, object_id: str, default: int = 0) -> int:
    """Прочитать счётчик. Если ключа нет — вернуть default."""
    key = _ck(prefix, object_id)
    value = cache.get(key)
    if value is not None:
        return int(value)
    return default


def get_or_seed_counter(
    prefix: str,
    object_id: str,
    qs: QuerySet,
) -> int:
    """Прочитать счётчик. Если ключа нет — подсчитать в БД и сохранить."""
    key = _ck(prefix, object_id)
    value = cache.get(key)
    if value is not None:
        return int(value)
    count = qs.aggregate(c=Count('pk'))['c'] or 0
    cache.set(key, count)
    logger.debug(
        'Счётчик инициализирован из БД: key=%s, count=%d',
        key, count,
    )
    return count


# =============================================================================
# CacheRetrieveMixin — кэширование retrieve с per-user ключом
# =============================================================================


class CacheRetrieveMixin:
    """Кэширует retrieve с per-user ключом.

    Ключ: '{prefix}:detail:{lookup_value}:{user_id}'.
    Каждый пользователь имеет свой кэш — персонализированные поля
    (is_liked_by_me, is_participant) всегда актуальны.

    Пример:
        class ProjectViewSet(CacheRetrieveMixin, ModelViewSet):
            retrieve_cache_timeout = 600
            retrieve_cache_key_prefix = 'projects'
    """

    retrieve_cache_timeout = 600
    retrieve_cache_key_prefix = ''

    def _get_user_part(self, request: Request) -> str:
        """Pk пользователя или 'anonymous' для неаутентифицированных."""
        user = request.user
        return str(getattr(user, 'pk', 'anonymous'))

    def retrieve(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Кэширует retrieve-запрос с per-user ключом."""
        lookup_value = kwargs.get(self.lookup_field, '')
        user_part = self._get_user_part(request)
        cache_key = (
            f'{self.retrieve_cache_key_prefix}:detail:'
            f'{lookup_value}:{user_part}'
        )

        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f'Cache HIT: {cache_key}')
            return Response(cached_response)

        logger.debug(f'Cache MISS: {cache_key}')
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=self.retrieve_cache_timeout,
            )

        return response
