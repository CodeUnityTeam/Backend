import logging
from datetime import timedelta
from functools import partial
from typing import Any, Union
from uuid import UUID

from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    CACHE_KEY_QNA_PREFIX,
    CACHE_KEY_RESPONSES_PREFIX,
    CACHE_KEY_USERS_PREFIX,
)
from core.constants.feedback import FEEDBACK_STATUS_CLOSED
from core.constants.projects import ARCHIVED
from core.constants.users import LAST_LOGIN_UPDATE_INTERVAL
from minio.s3_utils import MediaType, S3Service
from projects.models import Response as ProjectResponse
from users.models.users import User
from users.selectors import (
    get_employer_base_queryset,
    get_employer_profiles_selector,
)

logger = logging.getLogger(__name__)


def avatar_upload_handler(
    user: User,
    file_obj: UploadedFile,
) -> str:
    """Бизнес-логика загрузки аватара с гарантией целостности БД."""
    old_avatar_url: str = getattr(user, 'avatar_url', '')

    # 1. Загружаем в MinIO ВНЕ транзакции БД
    public_url: str = S3Service.upload(MediaType.AVATAR, file_obj)

    # 2. Атомарно сохраняем изменения в БД
    with transaction.atomic():
        setattr(user, 'avatar_url', public_url)
        user.save(update_fields=('avatar_url',))
        logger.debug(
            'Новый аватар загружен в S3: user_id=%s, avatar_url=%s, size=%s '
            'avatar_name=%s',
            user.user_id,
            public_url,
            file_obj.size,
            file_obj.name,
        )

        # 3. Удаляем старый файл только после успешного коммита транзакции
        if old_avatar_url:
            transaction.on_commit(
                lambda url=old_avatar_url: S3Service.delete(
                    MediaType.AVATAR,
                    url,
                ),
            )
            logger.debug(
                'Запланировано удаление старого аватара из S3: '
                'user_id=%s, old_avatar_url=%s',
                user.user_id,
                old_avatar_url,
            )

    return public_url


def avatar_delete_handler(user: User) -> None:
    """Бизнес-логика удаления аватара."""
    old_avatar_url: str = getattr(user, 'avatar_url', '')

    with transaction.atomic():
        setattr(user, 'avatar_url', '')
        user.save(update_fields=('avatar_url',))

        if old_avatar_url:
            transaction.on_commit(
                lambda url=old_avatar_url: S3Service.delete(
                    MediaType.AVATAR,
                    url,
                ),
            )


def _invalidate_deactivated_user_cache(
    user_id: Any,
    project_ids: tuple[Any, ...],
    response_feed_user_ids: tuple[Any, ...],
) -> None:
    """Очистить кэш, затронутый мягким удалением пользователя."""
    for project_id in project_ids:
        cache.delete_pattern(
            f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
        )

    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:list:ids:*')
    cache.delete_pattern(f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:*')

    for feed_user_id in response_feed_user_ids:
        cache.delete_pattern(
            f'{CACHE_KEY_RESPONSES_PREFIX}:feed:{feed_user_id}:*',
        )

    logger.debug(
        'Кэш после деактивации пользователя очищен: user_id=%s, '
        'projects=%s, response_feeds=%s',
        user_id,
        len(project_ids),
        len(response_feed_user_ids),
    )


def deactivate_user_account(user: User) -> None:
    """Выполнить мягкое удаление пользователя и обработать связанные сущности.

    - Переводит FeedbackForm в статус Closed
    - Переводит проекты в статус ARCHIVED
    - Удаляет записи ProjectParticipant
    - Удаляет отклики Response
    - Сбрасывает активность пользователя и верификацию email
    """
    logger.info(
        'Деактивация пользователя: user_id=%s, email=%s',
        user.user_id,
        user.email,
    )
    with transaction.atomic():
        authored_project_ids = set(
            user.projects.values_list('project_id', flat=True),
        )
        participation_project_ids = set(
            user.project_participations.values_list(
                'project_id',
                flat=True,
            ),
        )
        response_project_ids = set(
            user.responses.values_list('project_id', flat=True),
        )
        affected_project_ids = tuple(
            authored_project_ids
            | participation_project_ids
            | response_project_ids,
        )

        response_feed_user_ids = set(
            ProjectResponse.objects.filter(
                project__author=user,
            ).values_list('user_id', flat=True),
        )
        response_feed_user_ids.add(user.user_id)

        # 1. Закрываем формы обратной связи
        closed_count = user.feedback_forms.update(
            status=FEEDBACK_STATUS_CLOSED,
        )
        logger.debug(
            'Закрыто форм обратной связи: user_id=%s, count=%s',
            user.user_id,
            closed_count,
        )

        # 2. Архивируем проекты автора
        archived_count = user.projects.update(status_project=ARCHIVED)
        logger.debug(
            'Архивировано проектов: user_id=%s, count=%s',
            user.user_id,
            archived_count,
        )

        # 3. Удаляем участия в проектах
        participations_count = user.project_participations.all().delete()[0]
        logger.debug(
            'Удалено участий в проектах: user_id=%s, count=%s',
            user.user_id,
            participations_count,
        )

        # 4. Удаляем отклики и приглашения
        responses_count = user.responses.all().delete()[0]
        logger.debug(
            'Удалено откликов: user_id=%s, count=%s',
            user.user_id,
            responses_count,
        )

        # 5. Деактивируем самого пользователя
        user.is_active = False
        user.is_agreed_to_terms = False
        user.save(update_fields=('is_active', 'is_agreed_to_terms'))

        # 6. Сбрасываем верификацию почты
        updated = EmailAddress.objects.filter(
            user=user,
            email__iexact=user.email,
        ).update(verified=False)
        logger.debug(
            'Сброшена верификация email: user_id=%s, updated=%s',
            user.user_id,
            updated,
        )

        transaction.on_commit(
            partial(
                _invalidate_deactivated_user_cache,
                user.user_id,
                affected_project_ids,
                tuple(response_feed_user_ids),
            ),
        )


def _is_valid_uuid(val: str) -> bool:
    """Проверяет, является ли строка валидным UUID."""
    try:
        UUID(val)
        return True
    except ValueError:
        return False


def get_profiles_for_employer_service(
    current_user: Any,
    query_params: dict[str, Any],
) -> Union[QuerySet[ProjectResponse], QuerySet[User]]:
    """Получить фильтрованный и сортированный список пользователей.

    Выбирает базовый queryset в зависимости от сценария запроса (все,
    избранное, отклики) и подготавливает данные для запроса в базу.
    """
    # 1. Определяем сценарий
    if query_params.get('responses', '').lower() == 'true':
        scenario: str = 'responses'
    elif query_params.get('favourites', '').lower() == 'true':
        scenario = 'favourites'
    else:
        scenario = 'all'

    # Бизнес-исключение: одновременный вызов responses и favourites запрещен
    if (
        query_params.get('responses', '').lower() == 'true'
        and query_params.get('favourites', '').lower() == 'true'
    ):
        return User.objects.none()

    # 2. Инициализируем базовые параметры таблиц СУБД под сценарий
    if scenario == 'responses':
        base_queryset: QuerySet[Any] = (
            ProjectResponse.objects
            .filter(
                project__author=current_user,
                user__is_active=True,
            )
            .exclude(user=current_user)
            .select_related('project', 'user')
        )
        outer_ref_field: str = 'user_id'
        field_prefix: str = 'user__'
    else:
        base_queryset = User.objects.filter(is_active=True).exclude(
            pk=current_user.pk,
        )
        outer_ref_field = 'pk'
        field_prefix = ''

    # 3. Чистим и парсим списки UUID
    sort_by: str = query_params.get('sort_by', 'newest').lower()
    raw_skills: str = query_params.get('skill_ids', '')
    raw_specs: str = query_params.get('spec_ids', '')
    raw_formats: str = query_params.get('format_ids', '')

    skill_ids: tuple[str, ...] = (
        tuple(filter(_is_valid_uuid, raw_skills.split(',')))
        if raw_skills
        else ()
    )
    spec_ids: tuple[str, ...] = (
        tuple(filter(_is_valid_uuid, raw_specs.split(',')))
        if raw_specs
        else ()
    )
    format_ids: tuple[str, ...] = (
        tuple(filter(_is_valid_uuid, raw_formats.split(',')))
        if raw_formats
        else ()
    )

    # 4. Вызываем общий для всех запросов селектор
    annotated_queryset = get_employer_base_queryset(
        current_user=current_user,
        outer_ref_field=outer_ref_field,
        field_prefix=field_prefix,
        sort_by=sort_by,
        skill_ids=skill_ids,
        spec_ids=spec_ids,
        format_ids=format_ids,
        queryset=base_queryset,
    )

    # 5. Передаем готовый QuerySet в сценарный маппер
    return get_employer_profiles_selector(
        scenario=scenario,
        current_user=current_user,
        queryset=annotated_queryset,
    )


def update_last_login(user: User) -> None:
    """Обновить last_login пользователя, если прошло достаточно времени.

    Обновляет поле last_login в БД,
    но не чаще одного раза в LAST_LOGIN_UPDATE_INTERVAL.
    """
    now = timezone.now()
    last_login = user.last_login
    if not last_login or (now - last_login) > timedelta(
        minutes=LAST_LOGIN_UPDATE_INTERVAL,
    ):
        user_id = user.pk
        User.objects.filter(pk=user_id).update(last_login=now)
        user.last_login = now

        def invalidate() -> None:
            from projects.models import Project

            cache.delete_pattern(
                f'{CACHE_KEY_USERS_PREFIX}:detail:{user_id}:*',
            )
            project_ids = Project.objects.filter(
                Q(author_id=user_id) | Q(participants__user_id=user_id),
            ).values_list('project_id', flat=True).distinct()
            for project_id in project_ids:
                cache.delete_pattern(
                    f'{CACHE_KEY_PROJECTS_PREFIX}:detail:{project_id}:*',
                )

        transaction.on_commit(invalidate)


def update_user_rating(user: User, delta: int) -> None:
    """Обновляет рейтинг пользователя при постановке/снятии лайка."""
    user_id = user.pk
    User.objects.filter(pk=user_id).update(
        rating=F('rating') + delta,
    )

    def invalidate() -> None:
        from qna.models import Question

        cache.delete_pattern(
            f'{CACHE_KEY_USERS_PREFIX}:detail:{user_id}:*',
        )
        question_ids = Question.objects.filter(
            Q(user_id=user_id) | Q(answers__user_id=user_id),
        ).values_list('question_id', flat=True).distinct()
        for question_id in question_ids:
            cache.delete_pattern(
                f'{CACHE_KEY_QNA_PREFIX}:detail:{question_id}:*',
            )

    transaction.on_commit(invalidate)
    logger.debug(
        'Рейтинг пользователя обновлён: user_id=%s, delta=%s',
        user_id,
        delta,
    )
