from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_RESPONSES_PREFIX,
)
from projects.models import Project, ProjectLike, ProjectParticipant, Response


@receiver(post_save, sender=Project)
@receiver(post_delete, sender=Project)
def invalidate_project_cache(
    sender: Any,
    instance: Project,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш проекта при создании/изменении/удалении.

    Очищает детали, список и рекомендации — для всех пользователей.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{instance.project_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:list:*')
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:*')


@receiver(post_save, sender=ProjectLike)
@receiver(post_delete, sender=ProjectLike)
def invalidate_project_like_cache(
    sender: Any,
    instance: ProjectLike,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при лайке/снятии лайка проекта.

    Очищает детали и список — только для пользователя, поставившего лайк
    (cache stampede prevention).
    """
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:'
        f'{instance.project_id}:{instance.user_id}',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:list:{instance.user_id}:*',
    )


@receiver(post_save, sender=Response)
@receiver(post_delete, sender=Response)
def invalidate_response_feed_cache(
    sender: Any,
    instance: Response,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш ленты откликов при создании/изменении/удалении.

    Очищает кэш для автора отклика и автора проекта
    (если это разные пользователи).
    """
    # Инвалидируем кэш для пользователя, который создал отклик
    cache.delete_pattern(
        f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{instance.user_id}:*',
    )

    # Инвалидируем кэш для автора проекта (если это не тот же пользователь)
    author_id = instance.project.author_id
    if str(author_id) != str(instance.user_id):
        cache.delete_pattern(
            f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{author_id}:*',
        )


@receiver(post_save, sender=ProjectParticipant)
@receiver(post_delete, sender=ProjectParticipant)
def invalidate_project_participant_cache(
    sender: Any,
    instance: ProjectParticipant,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш деталей проекта при изменении состава участников.

    Очищает детали проекта для всех пользователей.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{instance.project_id}:*',
    )
