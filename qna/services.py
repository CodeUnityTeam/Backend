from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from config import settings
from core.s3_utils import MinioService
from qna.models import AnswerImage, QuestionImage

image_minio_client = MinioService(
    bucket_name=settings.STORAGES["images"]["OPTIONS"]["bucket_name"],
)


def image_upload_handler(file_obj: UploadedFile) -> str:
    """Загружает изображение в MinIO ВНЕ транзакции БД.

    Возвращает публичный URL.
    """
    file_name_parts: list[str] = file_obj.name.split(".")
    ext: str = (
        file_name_parts[-1].lower() if len(file_name_parts) > 1 else "jpg"
    )
    cloud_path: str = f"{uuid4().hex}.{ext}"

    return image_minio_client.upload_file(cloud_path, file_obj)


def question_image_delete_handler(image: QuestionImage) -> None:
    """Удаление изображения вопроса с гарантией целостности БД."""
    image_url: str = image.image_url

    with transaction.atomic():
        image.delete()

        if image_url:
            transaction.on_commit(
                lambda: image_minio_client.delete_file(image_url),
            )


def answer_image_delete_handler(image: AnswerImage) -> None:
    """Удаление изображения ответа с гарантией целостности БД."""
    image_url: str = image.image_url

    with transaction.atomic():
        image.delete()

        if image_url:
            transaction.on_commit(
                lambda: image_minio_client.delete_file(image_url),
            )
