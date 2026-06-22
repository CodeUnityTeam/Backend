from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_USERS_PREFIX,
)
from users.models import User
from users.models.users import UserLike


@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def invalidate_user_profile_cache(
    sender: Any,
    instance: User,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при изменении профиля пользователя.

    Очищает детали и список профилей (для всех), а также
    рекомендации проектов для этого пользователя.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:detail:{instance.user_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:*')
    cache.delete(
        f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{instance.user_id}',
    )


@receiver(post_save, sender=UserLike)
@receiver(post_delete, sender=UserLike)
def invalidate_user_like_cache(
    sender: Any,
    instance: UserLike,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при лайке/снятии лайка пользователя.

    Очищает список профилей и детали профиля, которому поставили лайк
    — только для автора лайка (cache stampede prevention).
    """
    # Инвалидируем список профилей для автора лайка
    cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:list:{instance.employer_id}:*',
    )
    # Инвалидируем детали профиля для автора лайка
    cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:detail:'
        f'{instance.worker_id}:{instance.employer_id}',
    )