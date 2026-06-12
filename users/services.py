from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from config import settings
from core.s3_utils import MinioService
from users.models.users import User

avatar_minio_client = MinioService(
    bucket_name=settings.STORAGES['avatars']['OPTIONS']['bucket_name'],
)


def avatar_upload_handler(
    user: User,
    file_obj: UploadedFile,
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
        cloud_path,
        file_obj,
    )

    # 2. Атомарно сохраняем изменения в БД
    with transaction.atomic():
        setattr(user, 'avatar_url', public_url)
        user.save(update_fields=['avatar_url'])

        # 3. Удаляем старый файл только после успешного коммита транзакции
        if old_avatar_url:
            transaction.on_commit(
                lambda: avatar_minio_client.delete_file(old_avatar_url),
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
