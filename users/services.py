from functools import partial
from typing import Any, Union
from uuid import UUID, uuid4

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet

from config import settings
from core.s3_utils import MinioService
from projects.models import Response as ProjectResponse
from users.models.users import User
from users.selectors import (
    get_employer_base_queryset,
    get_employer_profiles_selector,
)

avatar_minio_client = MinioService(
    bucket_name=settings.STORAGES['avatars']['OPTIONS']['bucket_name'],
)


def avatar_upload_handler(
    user: User, file_obj: UploadedFile,
) -> str:
    """Бизнес-логика загрузки аватара с гарантией целостности БД."""
    old_avatar_url: str = getattr(user, 'avatar_url', '')

    # 1. Генерируем путь и загружаем в MinIO ВНЕ транзакции БД
    file_name_parts: list[str] = file_obj.name.split('.')
    ext: str = (
        file_name_parts[-1].lower() if len(file_name_parts) > 1 else 'png'
    )
    random_filename: str = uuid4().hex
    cloud_path: str = f'avatars/{random_filename}.{ext}'

    public_url: str = avatar_minio_client.upload_file(
        cloud_path, file_obj,
    )

    # 2. Атомарно сохраняем изменения в БД
    with transaction.atomic():
        setattr(user, 'avatar_url', public_url)
        user.save(update_fields=['avatar_url'])

        # 3. Удаляем старый файл только после успешного коммита транзакции
        if old_avatar_url:
            transaction.on_commit(
                partial(avatar_minio_client.delete_file, old_avatar_url),
            )

    return public_url


def avatar_delete_handler(user: User) -> None:
    """Бизнес-логика удаления аватара."""
    old_avatar_url: str = getattr(user, 'avatar_url', '')

    with transaction.atomic():
        setattr(user, 'avatar_url', '')
        user.save(update_fields=['avatar_url'])

        if old_avatar_url:
            transaction.on_commit(
                lambda: avatar_minio_client.delete_file(old_avatar_url),
            )


def _is_valid_uuid(val: str) -> bool:
    """Проверяет, является ли строка валидным UUID."""
    try:
        UUID(val)
        return True
    except ValueError:
        return False


def get_profiles_for_employer_service(
    current_user: Any, query_params: dict[str, Any],
) -> Union[QuerySet[ProjectResponse], QuerySet[User]]:
    """Получить фильтрованный и сортированный список пользователей.

    Выбитрает базовый queryset в зависимости от сценария запроса (все,
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
            ProjectResponse.objects.filter(project__author=current_user)
            .exclude(user=current_user)
            .select_related('project', 'user')
        )
        outer_ref_field: str = 'user_id'
        field_prefix: str = 'user__'
    else:
        base_queryset = User.objects.exclude(pk=current_user.pk)
        outer_ref_field = 'pk'
        field_prefix = ''

    # 3. Чистим и парсим списки UUID
    sort_by: str = query_params.get('sort_by', 'newest').lower()
    raw_skills: str = query_params.get('skill_ids', '')
    raw_specs: str = query_params.get('spec_ids', '')
    raw_formats: str = query_params.get('format_ids', '')

    skill_ids: tuple[str, ...] = (
        tuple(filter(_is_valid_uuid, raw_skills.split(',')))
        if raw_skills else ()
    )
    spec_ids: tuple[str, ...] = (
        tuple(filter(_is_valid_uuid, raw_specs.split(',')))
        if raw_specs else ()
    )
    format_ids: tuple[str, ...] = (
        tuple(filter(_is_valid_uuid, raw_formats.split(',')))
        if raw_formats else ()
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
