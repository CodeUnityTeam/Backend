import logging
from typing import Any

from django.core.cache import cache
from django.db.models import Count, QuerySet
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# =============================================================================
# Счётчики в Redis (cache-aside)
# =============================================================================


def _ck(prefix: str, object_id: str) -> str:
    """Сформировать ключ Redis для счётчика."""
    return f'{prefix}:{object_id}'


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
        if not user.is_authenticated:
            return 'anonymous'
        return str(user.pk)

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
            logger.debug('Cache HIT: %s', cache_key)
            return Response(cached_response)

        logger.debug('Cache MISS: %s', cache_key)
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=self.retrieve_cache_timeout,
            )

        return response
