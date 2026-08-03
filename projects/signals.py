import logging
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
)
from django.dispatch import receiver

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_RESPONSES_PREFIX,
    CACHE_KEY_USERS_PREFIX,
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


def _delete_counter(prefix: str, object_id: Any) -> None:
    """Удалить счётчик, чтобы следующее чтение восстановило его из БД."""
    cache.delete(f'{prefix}:{object_id}')


def _invalidate_project(project_id: Any) -> None:
    """Очистить представления и списки, зависящие от данных проекта."""
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:*')
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:*')
    _delete_counter(COUNTER_PROJECT_LIKES_PREFIX, project_id)
    _delete_counter(COUNTER_PROJECT_PARTICIPANTS_PREFIX, project_id)
    logger.debug('Кэш проекта очищен: project_id=%s', project_id)


def _invalidate_project_like(project_id: Any) -> None:
    """Очистить данные, зависящие от лайков и сортировки по ним."""
    _delete_counter(COUNTER_PROJECT_LIKES_PREFIX, project_id)
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:*')
    logger.debug('Кэш лайков проекта очищен: project_id=%s', project_id)


def _invalidate_response(
    response_user_id: Any,
    project_id: Any,
    project_author_id: Any,
) -> None:
    """Очистить списки, чьи состав или фильтры зависят от отклика."""
    cache.delete_pattern(
        f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{response_user_id}:*',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:list:ids:{project_author_id}:*',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
    )


def _invalidate_participant(user_id: Any, project_id: Any) -> None:
    """Очистить кэш после изменения состава участников проекта."""
    _delete_counter(COUNTER_PROJECT_PARTICIPANTS_PREFIX, project_id)
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{user_id}:*',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{user_id}:*',
    )


def _invalidate_favorite(user_id: Any, project_id: Any) -> None:
    """Очистить персональные представления после изменения избранного."""
    cache.delete(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:{user_id}',
    )
    cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{user_id}:*',
    )


@receiver(post_save, sender=Project)
@receiver(post_delete, sender=Project)
def invalidate_project_cache(
    sender: Any,
    instance: Project,
    **kwargs: Any,
) -> None:
    """Запланировать полную инвалидацию изменённого проекта."""
    project_id = instance.project_id
    transaction.on_commit(
        lambda project_id=project_id: _invalidate_project(project_id),
    )


@receiver(m2m_changed, sender=Project.skills.through)
@receiver(m2m_changed, sender=Project.specializations.through)
@receiver(m2m_changed, sender=Project.project_format.through)
def invalidate_project_m2m_cache(
    sender: Any,
    instance: Any,
    action: str,
    **kwargs: Any,
) -> None:
    """Инвалидировать проект после изменения его фильтруемых M2M-полей."""
    reverse = kwargs.get('reverse', False)
    if reverse:
        if action in {'post_add', 'post_remove'}:
            project_ids = tuple(kwargs.get('pk_set') or ())
        elif action == 'pre_clear':
            project_ids = tuple(
                instance.projects.values_list('project_id', flat=True),
            )
        else:
            return
    elif action in {'post_add', 'post_remove', 'pre_clear'}:
        project_ids = (instance.project_id,)
    else:
        return

    for project_id in project_ids:
        transaction.on_commit(
            lambda project_id=project_id: _invalidate_project(project_id),
        )


@receiver(post_save, sender=ProjectLike)
@receiver(post_delete, sender=ProjectLike)
def invalidate_project_like_cache(
    sender: Any,
    instance: ProjectLike,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию счётчика и сортировки по лайкам."""
    project_id = instance.project_id
    transaction.on_commit(
        lambda project_id=project_id: _invalidate_project_like(project_id),
    )


@receiver(post_save, sender=Response)
@receiver(post_delete, sender=Response)
def invalidate_response_cache(
    sender: Any,
    instance: Response,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию ленты и списка откликов работодателя."""
    response_user_id = instance.user_id
    project_id = instance.project_id
    project_author_id = instance.project.author_id
    transaction.on_commit(
        lambda response_user_id=response_user_id,
        project_id=project_id,
        project_author_id=project_author_id: _invalidate_response(
            response_user_id,
            project_id,
            project_author_id,
        ),
    )


@receiver(post_save, sender=ProjectParticipant)
@receiver(post_delete, sender=ProjectParticipant)
def invalidate_project_participant_cache(
    sender: Any,
    instance: ProjectParticipant,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию состава участников и счётчика."""
    user_id = instance.user_id
    project_id = instance.project_id
    transaction.on_commit(
        lambda user_id=user_id, project_id=project_id: (
            _invalidate_participant(user_id, project_id)
        ),
    )


@receiver(post_save, sender=ProjectFavorite)
@receiver(post_delete, sender=ProjectFavorite)
def invalidate_favorite_cache(
    sender: Any,
    instance: ProjectFavorite,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию персонального избранного."""
    user_id = instance.user_id
    project_id = instance.project_id
    transaction.on_commit(
        lambda user_id=user_id, project_id=project_id: (
            _invalidate_favorite(user_id, project_id)
        ),
    )
