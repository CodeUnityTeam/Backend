import logging
from typing import Any

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.http import HttpRequest

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_USERS_PREFIX,
)
from users.models import User
from users.models.users import UserLike

CRITICAL_LIST_FIELDS = {
    'first_name',
    'last_name',
    'city',
    'country',
    'avatar_url',
    'rating',
    'is_active',
    'projects_relation',
}


logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def invalidate_user_profile_save(
    sender: Any,
    instance: User,
    update_fields: Any = None,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш профиля и списков при сохранении пользователя."""
    cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:detail:{instance.user_id}:*',
    )
    cache.delete(
        f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{instance.user_id}',
    )

    is_created = kwargs.get('created', False)
    should_invalidate_list = (
        is_created
        or update_fields is None
        or bool(set(update_fields) & CRITICAL_LIST_FIELDS)
    )

    if should_invalidate_list:
        cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:*')

    logger.debug(
        'Кэш пользователя инвалидирован post_save: user_id=%s, '
        'created=%s, update_fields=%s, list_invalidated=%s',
        instance.user_id,
        is_created,
        update_fields,
        should_invalidate_list,
    )


@receiver(post_delete, sender=User)
def invalidate_user_profile_delete(
    sender: Any,
    instance: User,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш профиля и списков при удалении пользователя."""
    cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:detail:{instance.user_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:*')
    cache.delete(
        f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{instance.user_id}',
    )
    logger.debug(
        'Кэш пользователя инвалидирован post_delete: user_id=%s',
        instance.user_id,
    )


@receiver(m2m_changed, sender=User.skills.through)
@receiver(m2m_changed, sender=User.specializations.through)
@receiver(m2m_changed, sender=User.workformats.through)
def invalidate_user_m2m_cache(
    sender: Any,
    instance: User,
    action: str,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при изменении Many-to-Many связей пользователя."""
    if action in ('post_add', 'post_remove', 'post_clear'):
        cache.delete_pattern(
            f'{CACHE_KEY_USERS_PREFIX}:detail:{instance.user_id}:*',
        )
        cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:*')
        logger.debug(
            'Кэш пользователя инвалидирован m2m_changed: user_id=%s, '
            'sender=%s, action=%s',
            instance.user_id,
            sender.__name__,
            action,
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
    logger.debug(
        'Кэш лайков пользователя инвалидирован: employer_id=%s, worker_id=%s',
        instance.employer_id,
        instance.worker_id,
    )


@receiver(email_confirmed)
def log_email_confirmed(
    request: HttpRequest,
    email_address: EmailAddress,
    **kwargs: Any,
) -> None:
    """Логирует успешное подтверждение email."""
    logger.info(
        'Email пользователя подтверждён. user=%s, email=%s',
        email_address.user,
        email_address.email,
    )
