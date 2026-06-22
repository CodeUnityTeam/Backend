import logging

from django.core.cache import cache
from rest_framework.response import Response

logger = logging.getLogger(__name__)


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

    def _get_user_part(self, request) -> str:
        """pk пользователя или 'anonymous' для неаутентифицированных."""
        user = request.user
        return str(getattr(user, 'pk', 'anonymous'))

    def retrieve(self, request, *args, **kwargs):
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
