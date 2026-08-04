import logging
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_QNA_PREFIX,
    CACHE_KEY_SKILLS_PREFIX,
    CACHE_KEY_SPECIALIZATIONS_PREFIX,
    CACHE_KEY_USERS_PREFIX,
    CACHE_KEY_WORK_FORMATS_PREFIX,
)
from projects.models import WorkFormat
from users.models import Skill, Specialization

logger = logging.getLogger(__name__)


def _invalidate_reference_cache(
    cache_key: str,
    invalidate_qna: bool = False,
) -> None:
    """Очистить представления, содержащие изменённый справочник."""
    cache.delete(cache_key)
    cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:detail:*')
    cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:ids:*')
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:detail:*')
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:*')
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:*')
    if invalidate_qna:
        cache.delete_pattern(f'{CACHE_KEY_QNA_PREFIX}:detail:*')
        cache.delete_pattern(f'{CACHE_KEY_QNA_PREFIX}:list:ids:*')


@receiver(post_save, sender=Skill)
@receiver(post_delete, sender=Skill)
def invalidate_skill_cache(sender: Any, **kwargs: Any) -> None:
    """Инвалидирует кэш навыков при создании/изменении/удалении.

    Ключ кэша: skills:list (см. help/views.py TagsListAPIView.list).
    """
    cache_key = f'{CACHE_KEY_SKILLS_PREFIX}:list'
    transaction.on_commit(
        lambda cache_key=cache_key: _invalidate_reference_cache(
            cache_key,
            invalidate_qna=True,
        ),
    )
    logger.info(
        'Инвалидация кэша навыков: cache_key=%s',
        cache_key,
    )


@receiver(post_save, sender=Specialization)
@receiver(post_delete, sender=Specialization)
def invalidate_specialization_cache(sender: Any, **kwargs: Any) -> None:
    """Инвалидирует кэш специализаций при создании/изменении/удалении.

    Ключ кэша: specializations:list (см. help/views.py TagsListAPIView.list).
    """
    cache_key = f'{CACHE_KEY_SPECIALIZATIONS_PREFIX}:list'
    transaction.on_commit(
        lambda cache_key=cache_key: _invalidate_reference_cache(cache_key),
    )
    logger.info(
        'Инвалидация кэша специализаций: cache_key=%s',
        cache_key,
    )


@receiver(post_save, sender=WorkFormat)
@receiver(post_delete, sender=WorkFormat)
def invalidate_work_format_cache(sender: Any, **kwargs: Any) -> None:
    """Инвалидирует кэш форматов работы при создании/изменении/удалении.

    Ключ кэша: work_formats:list (см. help/views.py TagsListAPIView.list).
    """
    cache_key = f'{CACHE_KEY_WORK_FORMATS_PREFIX}:list'
    transaction.on_commit(
        lambda cache_key=cache_key: _invalidate_reference_cache(cache_key),
    )
    logger.info(
        'Инвалидация кэша форматов работы: cache_key=%s',
        cache_key,
    )
