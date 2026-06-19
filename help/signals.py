from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.constants.cache import (
    CACHE_KEY_SKILLS_PREFIX,
    CACHE_KEY_SPECIALIZATIONS_PREFIX,
    CACHE_KEY_WORK_FORMATS_PREFIX,
)
from projects.models import WorkFormat
from users.models import Skill, Specialization


@receiver(post_save, sender=Skill)
@receiver(post_delete, sender=Skill)
def invalidate_skill_cache(sender: Any, **kwargs: Any) -> None:
    """Инвалидирует кэш навыков при создании/изменении/удалении."""
    cache.delete_pattern(f'{CACHE_KEY_SKILLS_PREFIX}:*')


@receiver(post_save, sender=Specialization)
@receiver(post_delete, sender=Specialization)
def invalidate_specialization_cache(sender: Any, **kwargs: Any) -> None:
    """Инвалидирует кэш специализаций при создании/изменении/удалении."""
    cache.delete_pattern(f'{CACHE_KEY_SPECIALIZATIONS_PREFIX}:*')


@receiver(post_save, sender=WorkFormat)
@receiver(post_delete, sender=WorkFormat)
def invalidate_work_format_cache(sender: Any, **kwargs: Any) -> None:
    """Инвалидирует кэш форматов работы при создании/изменении/удалении."""
    cache.delete_pattern(f'{CACHE_KEY_WORK_FORMATS_PREFIX}:*')
