from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.constants.cache import CACHE_KEY_REVIEWS_PREFIX
from feedback.models import Review


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def invalidate_review_cache(
    sender: Any,
    instance: Review,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при создании/изменении/удалении отзыва.

    Очищает:
    - детали отзыва — для всех пользователей
    - список отзывов — полностью (данные публичные)
    """
    cache.delete_pattern(
        f'{CACHE_KEY_REVIEWS_PREFIX}:detail:{instance.review_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_REVIEWS_PREFIX}:list:*')