from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from core.s3_utils import MinioService

feedback_image_minio_client = MinioService(
    bucket_name=settings.STORAGES['images']['OPTIONS']['bucket_name'],
)


def feedback_image_upload_handler(file_obj: UploadedFile) -> str:
    """Загружает изображение для обратной связи в MinIO.

    Генерирует уникальное имя файла на основе UUID,
    загружает в бакет и возвращает публичный URL.

    Args:
        file_obj: Загруженный файл от пользователя.

    Returns:
        Публичный URL загруженного изображения.

    """
    file_name_parts: list[str] = file_obj.name.split('.')
    ext: str = (
        file_name_parts[-1].lower() if len(file_name_parts) > 1 else 'jpg'
    )
    cloud_path: str = f'{uuid4().hex}.{ext}'

    return feedback_image_minio_client.upload_file(cloud_path, file_obj)
