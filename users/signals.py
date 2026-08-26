import logging
from functools import partial
from typing import Any

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.http import HttpRequest

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_QNA_PREFIX,
    CACHE_KEY_RESPONSES_PREFIX,
    CACHE_KEY_USERS_PREFIX,
)
from users.models import User, UserExperience
from users.models.users import UserLike

CRITICAL_LIST_FIELDS = {
    'first_name',
    'last_name',
    'city',
    'country',
    'is_active',
    'projects_relation',
}

PROJECT_LIST_VIEWER_FIELDS = {
    'projects_relation',
    'role',
    'is_staff',
    'is_superuser',
}

DETAIL_VIEWER_FIELDS = {
    'projects_relation',
    'is_active',
}

PROJECT_REPRESENTATION_FIELDS = {
    'first_name',
    'last_name',
    'email',
    'additional_contact',
    'avatar_url',
    'last_login',
}

QNA_REPRESENTATION_FIELDS = {
    'first_name',
    'last_name',
    'email',
    'avatar_url',
    'rating',
}

logger = logging.getLogger(__name__)


def _fields_changed(
    update_fields: Any,
    dependent_fields: set[str],
) -> bool:
    """Проверить, могло ли сохранение изменить зависимые поля."""
    return update_fields is None or bool(
        set(update_fields) & dependent_fields,
    )


def _invalidate_user_base_cache(
    user_id: Any,
    invalidate_lists: bool,
) -> None:
    """Очистить detail пользователя и при необходимости списки профилей."""
    redis_cache: Any = cache
    redis_cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:detail:{user_id}:*')
    if invalidate_lists:
        redis_cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:*')


def _invalidate_viewer_cache(user_id: Any) -> None:
    """Очистить JSON-кэш, где пользователь является просматривающим."""
    redis_cache: Any = cache
    redis_cache.delete_pattern(
        f'{CACHE_KEY_USERS_PREFIX}:detail:*:{user_id}',
    )
    redis_cache.delete_pattern(
        f'{CACHE_KEY_PROJECTS_PREFIX}:detail:*:{user_id}',
    )


def _invalidate_user_project_cache(user_id: Any) -> None:
    """Очистить project JSON, содержащий данные автора или участника."""
    from projects.models import Project, Response

    redis_cache: Any = cache
    project_ids = Project.objects.filter(
        Q(author_id=user_id) | Q(participants__user_id=user_id),
    ).values_list('project_id', flat=True).distinct()
    for project_id in project_ids:
        redis_cache.delete_pattern(
            f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
        )

    feed_user_ids = set(
        Response.objects.filter(
            project__author_id=user_id,
        ).values_list('user_id', flat=True),
    )
    feed_user_ids.add(user_id)
    for feed_user_id in feed_user_ids:
        redis_cache.delete_pattern(
            f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{feed_user_id}:*',
        )


def _invalidate_user_qna_cache(user_id: Any) -> None:
    """Очистить detail вопросов, содержащих данные пользователя-автора."""
    from qna.models import Question

    redis_cache: Any = cache
    question_ids = Question.objects.filter(
        Q(user_id=user_id) | Q(answers__user_id=user_id),
    ).values_list('question_id', flat=True).distinct()
    for question_id in question_ids:
        redis_cache.delete_pattern(
            f'{CACHE_KEY_QNA_PREFIX}:detail:{question_id}:*',
        )


def _invalidate_user_m2m_by_ids(
    user_ids: set[Any],
    skills_changed: bool,
) -> None:
    """Очистить кэши пользователей после прямого или обратного M2M."""
    redis_cache: Any = cache
    redis_cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:*')
    for user_id in user_ids:
        redis_cache.delete_pattern(
            f'{CACHE_KEY_USERS_PREFIX}:detail:{user_id}:*',
        )
        if skills_changed:
            redis_cache.delete_pattern(
                f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{user_id}:*',
            )


def _get_reverse_m2m_user_ids(
    instance: Any,
    action: str,
    pk_set: Any,
) -> set[Any] | None:
    """Получить затронутых пользователей для обратного M2M-события."""
    if action in ('post_add', 'post_remove'):
        return set(pk_set or ())
    if action == 'pre_clear':
        return set(instance.users.values_list('user_id', flat=True))
    return None


@receiver(post_save, sender=User)
def invalidate_user_profile_save(
    sender: Any, # noqa: ARG001
    instance: User,
    update_fields: Any = None,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию зависимых кэшей после коммита User."""
    user_id = instance.user_id
    is_created = kwargs.get('created', False)
    fields_to_check = update_fields or ()
    should_invalidate_list = (
        is_created
        or update_fields is None
        or bool(set(fields_to_check) & CRITICAL_LIST_FIELDS)
    )
    invalidate_project_data = (
        not is_created
        and _fields_changed(update_fields, PROJECT_REPRESENTATION_FIELDS)
    )
    invalidate_qna_data = (
        not is_created
        and _fields_changed(update_fields, QNA_REPRESENTATION_FIELDS)
    )
    invalidate_project_list = (
        not is_created
        and _fields_changed(update_fields, PROJECT_LIST_VIEWER_FIELDS)
    )
    invalidate_viewer_data = (
        not is_created
        and _fields_changed(update_fields, DETAIL_VIEWER_FIELDS)
    )

    def invalidate() -> None:
        _invalidate_user_base_cache(user_id, should_invalidate_list)
        redis_cache: Any = cache
        redis_cache.delete_pattern(
            f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{user_id}:*',
        )
        if invalidate_project_list:
            redis_cache.delete_pattern(
                f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{user_id}:*',
            )
        if invalidate_viewer_data:
            _invalidate_viewer_cache(user_id)
        if invalidate_project_data:
            _invalidate_user_project_cache(user_id)
        if invalidate_qna_data:
            _invalidate_user_qna_cache(user_id)

    transaction.on_commit(invalidate)

    logger.debug(
        'Инвалидация кэша пользователя запланирована: user_id=%s, '
        'created=%s, update_fields=%s, list_invalidated=%s',
        user_id,
        is_created,
        update_fields,
        should_invalidate_list,
    )


@receiver(post_delete, sender=User)
def invalidate_user_profile_delete(
    sender: Any, # noqa: ARG001
    instance: User,
    **kwargs: Any, # noqa: ARG001
) -> None:
    """Запланировать инвалидацию основных кэшей удалённого пользователя."""
    user_id = instance.user_id
    redis_cache: Any = cache

    def invalidate() -> None:
        _invalidate_user_base_cache(user_id, invalidate_lists=True)
        _invalidate_viewer_cache(user_id)
        redis_cache.delete_pattern(
            f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:{user_id}:*',
        )
        redis_cache.delete_pattern(
            f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:{user_id}:*',
        )
        redis_cache.delete_pattern(
            f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{user_id}:*',
        )

    transaction.on_commit(invalidate)
    logger.debug(
        'Инвалидация кэша удалённого пользователя запланирована: user_id=%s',
        user_id,
    )


@receiver(post_save, sender=UserExperience)
@receiver(post_delete, sender=UserExperience)
def invalidate_user_experience_cache(
    sender: Any, # noqa: ARG001
    instance: UserExperience,
    **kwargs: Any, # noqa: ARG001
) -> None:
    """Инвалидировать detail профиля после изменения опыта работы."""
    redis_cache: Any = cache
    user_id = instance.user_id
    transaction.on_commit(
        partial(
            redis_cache.delete_pattern,
            f'{CACHE_KEY_USERS_PREFIX}:detail:{user_id}:*',
        ),
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
    """Запланировать инвалидацию после изменения M2M профиля."""
    reverse = kwargs.get('reverse', False)
    skills_changed = sender is User.skills.through

    if reverse:
        user_ids = _get_reverse_m2m_user_ids(
            instance,
            action,
            kwargs.get('pk_set'),
        )
        if user_ids is None:
            return

        transaction.on_commit(
            partial(
                _invalidate_user_m2m_by_ids,
                user_ids,
                skills_changed,
            ),
        )
        logger.debug(
            'Инвалидация обратного M2M-кэша запланирована: sender=%s, '
            'action=%s, users=%d',
            sender.__name__,
            action,
            len(user_ids),
        )
        return

    if action not in ('post_add', 'post_remove', 'post_clear'):
        return

    user_id = instance.user_id

    def invalidate() -> None:
        _invalidate_user_m2m_by_ids(
            {user_id},
            skills_changed,
        )

    transaction.on_commit(invalidate)
    logger.debug(
        'Инвалидация M2M-кэша пользователя запланирована: user_id=%s, '
        'sender=%s, action=%s',
        user_id,
        sender.__name__,
        action,
    )


@receiver(post_save, sender=UserLike)
@receiver(post_delete, sender=UserLike)
def invalidate_user_like_cache(
    sender: Any, # noqa: ARG001
    instance: UserLike,
    **kwargs: Any, # noqa: ARG001
) -> None:
    """Инвалидировать сортировку профилей и персональное поле is_liked."""
    employer_id = instance.employer_id
    worker_id = instance.worker_id
    redis_cache: Any = cache

    def invalidate() -> None:
        redis_cache.delete_pattern(f'{CACHE_KEY_USERS_PREFIX}:list:ids:*')
        redis_cache.delete_pattern(
            f'{CACHE_KEY_USERS_PREFIX}:detail:{worker_id}:{employer_id}',
        )

    transaction.on_commit(invalidate)
    logger.debug(
        'Инвалидация кэша лайка пользователя запланирована: '
        'employer_id=%s, worker_id=%s',
        employer_id,
        worker_id,
    )


@receiver(email_confirmed)
def log_email_confirmed(
    request: HttpRequest, # noqa: ARG001
    email_address: EmailAddress,
    **kwargs: Any, # noqa: ARG001
) -> None:
    """Логирует успешное подтверждение email."""
    logger.info(
        'Email пользователя подтверждён. user=%s, email=%s',
        email_address.user,
        email_address.email,
    )
