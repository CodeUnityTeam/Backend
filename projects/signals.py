import logging
from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.cache_mixins import decr_counter, incr_counter
from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_RESPONSES_PREFIX,
    COUNTER_PROJECT_LIKES_PREFIX,
    COUNTER_PROJECT_PARTICIPANTS_PREFIX,
)
from projects.models import (
    Project,
    ProjectFavorite,
    ProjectLike,
    ProjectParticipant,
    Response,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
@receiver(post_delete, sender=Project)
def invalidate_project_cache(
    sender: Any,
    instance: Project,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш проекта при создании/изменении/удалении.

    Очищает:
    - детали проекта — для всех пользователей (меняются сами данные)
    - список проектов — только для автора (остальные видят те же данные)
    - рекомендации — для всех (появился/изменился проект)
    """
    project_id = instance.project_id
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{instance.author_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:*')
    logger.debug('Очищен кэш проекта %s', project_id)


@receiver(post_save, sender=ProjectLike)
@receiver(post_delete, sender=ProjectLike)
def invalidate_project_like_cache(
    sender: Any,
    instance: ProjectLike,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при лайке/снятии лайка проекта.

    - Обновляет счётчик лайков через incr/decr (без COUNT-запроса к БД).
    - Очищает детали и список — только для пользователя, поставившего лайк.
    """
    liked = kwargs.get('created', False)
    if liked:
        new_value = incr_counter(
            COUNTER_PROJECT_LIKES_PREFIX, str(instance.project_id),
        )
    else:
        new_value = decr_counter(
            COUNTER_PROJECT_LIKES_PREFIX, str(instance.project_id),
        )

    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:'
        f'{instance.project_id}:{instance.user_id}',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{instance.user_id}:*',
    )
    logger.debug(
        'Лайк проекта %s: liked=%s, счётчик лайков=%d, '
        'кэш пользователя %s инвалидирован',
        instance.project_id,
        liked,
        new_value,
        instance.user_id,
    )


@receiver(post_save, sender=Response)
@receiver(post_delete, sender=Response)
def invalidate_response_feed_cache(
    sender: Any,
    instance: Response,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш ленты откликов при создании/изменении/удалении.

    Очищает кэш ленты только для worker'а, создавшего отклик
    (instance.user_id).
    """
    cache.delete_pattern(
        f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{instance.user_id}:*',
    )


@receiver(post_save, sender=ProjectParticipant)
@receiver(post_delete, sender=ProjectParticipant)
def invalidate_project_participant_cache(
    sender: Any,
    instance: ProjectParticipant,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш деталей проекта при изменении состава участников.

    - Обновляет счётчик участников через incr/decr.
    - Очищает детали проекта для всех пользователей.
    """
    created = kwargs.get('created', False)
    if created:
        new_value = incr_counter(
            COUNTER_PROJECT_PARTICIPANTS_PREFIX,
            str(instance.project_id),
        )
    else:
        new_value = decr_counter(
            COUNTER_PROJECT_PARTICIPANTS_PREFIX,
            str(instance.project_id),
        )

    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{instance.project_id}:*',
    )
    logger.debug(
        'Участник проекта %s: added=%s, счётчик участников=%d',
        instance.project_id,
        created,
        new_value,
    )


@receiver(post_save, sender=Response)
@receiver(post_delete, sender=Response)
def invalidate_project_detail_on_response_change(
    sender: Any,
    instance: Response,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш, связанный с откликами.

    ВАЖНО: очищает кэш деталей проекта, чтобы при изменении
    статуса (pending -> approved) пользователь видел актуальное
    количество участников.
    """
    project_id = instance.project_id
    user_id = instance.user_id
    author_id = instance.project.author_id
    #  Инвалидируем кэш для АВТОРА проекта.
    cache.delete(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:{author_id}',
    )
    #  Инвалидируем кэш для ПОЛЬЗОВАТЕЛЯ, чей отклик изменился.
    cache.delete(f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:{user_id}')


@receiver(post_save, sender=ProjectFavorite)
@receiver(post_delete, sender=ProjectFavorite)
def invalidate_favorite_cache(
    sender: Any,
    instance: ProjectFavorite,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при добавлении/удалении проекта из избранного.

    Очищает:
    - детали проекта для конкретного пользователя
    - список проектов для конкретного пользователя
    """
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:'
        f'{instance.project_id}:{instance.user_id}',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{instance.user_id}:*',
    )
