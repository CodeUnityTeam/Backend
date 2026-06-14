from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.db.models import Model

from config import settings
from core.s3_utils import MinioService

image_minio_client = MinioService(
    bucket_name=settings.STORAGES['images']['OPTIONS']['bucket_name'],
)


def image_upload_handler(file_obj: UploadedFile) -> str:
    """Загружает изображение в MinIO ВНЕ транзакции БД.

    Возвращает публичный URL.
    """
    file_name_parts: list[str] = file_obj.name.split('.')
    ext: str = (
        file_name_parts[-1].lower() if len(file_name_parts) > 1 else 'jpg'
    )
    cloud_path: str = f'{uuid4().hex}.{ext}'

    return image_minio_client.upload_file(cloud_path, file_obj)


def toggle_like(
    like_model: type[Model],
    target_obj: Model,
    user: Model,
    target_field: str,
) -> dict:
    """Универсальный toggle-лайк.

    Создаёт или удаляет лайк и возвращает статус с количеством лайков.
    Избегает дополнительного COUNT запроса, используя агрегацию из БД.

    Args:
        like_model: Модель лайка (QuestionLike или AnswerLike).
        target_obj: Объект, который лайкают (Question или Answer).
        user: Пользователь, который ставит лайк.
        target_field: Имя поля в like_model для связи с target_obj.

    Returns:
        dict: {'liked': bool, 'likes_count': int}
    """
    like, created = like_model.objects.get_or_create(
        **{target_field: target_obj, 'user': user},
    )
    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    # Используем агрегацию из БД вместо .count() на prefetch-кеше,
    # чтобы избежать проблем с устаревшим кешем prefetch_related
    likes_count = like_model.objects.filter(
        **{target_field: target_obj},
    ).count()

    return {
        'liked': liked,
        'likes_count': likes_count,
    }
