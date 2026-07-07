from django.core.files.uploadedfile import UploadedFile

from core.s3_utils import MediaType, S3Service


def feedback_image_upload_handler(file_obj: UploadedFile) -> str:
    """Загружает изображение для обратной связи в MinIO.

    Args:
        file_obj: Загруженный файл от пользователя.

    Returns:
        Публичный URL загруженного изображения.

    """
    return S3Service.upload(MediaType.FEEDBACK_IMAGE, file_obj)
