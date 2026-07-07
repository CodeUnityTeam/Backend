import logging
from enum import StrEnum
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from storages.backends.s3boto3 import S3Boto3Storage

logger = logging.getLogger(__name__)


class MediaType(StrEnum):
    """Типы медиа-контента.

    Каждый тип соответствует отдельному бакету в S3/MinIO.
    Значение enum используется как префикс-директория внутри бакета.
    """

    AVATAR = 'avatars'
    QUESTION_IMAGE = 'questions'
    ANSWER_IMAGE = 'answers'
    FEEDBACK_IMAGE = 'feedback'
    PROJECT_IMAGE = 'projects'
    UPLOAD_IMAGE = 'images'


class S3Service:
    """Единый сервис для работы с S3/MinIO.

    При первом обращении к бакету автоматически создаёт его в S3/MinIO,
    если он ещё не существует.

    Usage:
        >>> from core.s3_utils import S3Service, MediaType
        >>> url = S3Service.upload(MediaType.AVATAR, file_obj)
        >>> S3Service.delete(MediaType.AVATAR, url)
    """

    _storages: dict[str, S3Boto3Storage] = {}

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    @classmethod
    def upload(
        cls,
        media_type: MediaType,
        file_obj: UploadedFile,
    ) -> str:
        """Загружает файл в S3 и возвращает публичный URL."""
        storage = cls._get_storage(media_type)
        cloud_path = cls._generate_cloud_path(media_type, file_obj.name)
        saved_name = storage.save(cloud_path, file_obj)
        return storage.url(saved_name)

    @classmethod
    def delete(cls, media_type: MediaType, file_url: str) -> None:
        """Удаляет файл из S3 по его публичному URL."""
        try:
            storage = cls._get_storage(media_type)
            bucket_name = cls._get_bucket_name(media_type)
            bucket_prefix = f'{bucket_name}/'
            if bucket_prefix in file_url:
                file_path = file_url.split(bucket_prefix)[-1]
                storage.delete(file_path)
        except Exception as err:
            logger.error(
                'Ошибка удаления файла %s (%s): %s',
                file_url, media_type, err,
            )
            raise

    @classmethod
    def generate_presigned_upload_url(
        cls,
        media_type: MediaType,
        filename: str,
        expires_in: int = 3600,
    ) -> dict:
        """Генерирует presigned URL для загрузки файла напрямую в S3.

        Позволяет фронтенду загружать файлы напрямую в S3 минуя Django.
        """
        storage = cls._get_storage(media_type)
        s3_client = storage.connection.meta.client
        bucket_name = cls._get_bucket_name(media_type)
        cloud_path = cls._generate_cloud_path(media_type, filename)

        url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': bucket_name,
                'Key': cloud_path,
            },
            ExpiresIn=expires_in,
        )

        return {
            'url': url,
            'object_key': cloud_path,
            'public_url': storage.url(cloud_path),
        }

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    @classmethod
    def _get_bucket_name(cls, media_type: MediaType) -> str:
        """Возвращает имя бакета для типа медиа из настроек."""
        return settings.S3_BUCKETS[media_type]

    @classmethod
    def _get_storage(cls, media_type: MediaType) -> S3Boto3Storage:
        """Лениво создаёт и кэширует S3Boto3Storage для типа медиа.

        При первом создании проверяет существование бакета
        и создаёт его, если он отсутствует.
        """
        bucket_name = cls._get_bucket_name(media_type)

        if bucket_name not in cls._storages:
            storage = cls._init_storage(bucket_name)
            cls._ensure_bucket_exists(storage, bucket_name)
            cls._storages[bucket_name] = storage

        return cls._storages[bucket_name]

    @classmethod
    def _init_storage(cls, bucket_name: str) -> S3Boto3Storage:
        """Инициализирует S3Boto3Storage для указанного бакета."""
        options = settings.STORAGES['s3']['OPTIONS']
        custom_domain = settings.S3_CUSTOM_DOMAIN

        storage = S3Boto3Storage(
            access_key=options.get('access_key'),
            secret_key=options.get('secret_key'),
            bucket_name=bucket_name,
            endpoint_url=options.get('endpoint_url'),
            custom_domain=(
                f'{custom_domain}/{bucket_name}' if custom_domain else None
            ),
            querystring_auth=False,
            file_overwrite=False,
        )

        # Cache-Control для иммутабельных файлов.
        # Все файлы имеют UUID в имени, поэтому новый файл = новый URL.
        storage.object_parameters['CacheControl'] = (
            'public, max-age=31536000, immutable'
        )

        return storage

    @classmethod
    def _ensure_bucket_exists(
        cls,
        storage: S3Boto3Storage,
        bucket_name: str,
    ) -> None:
        """Проверяет существование бакета и создаёт его при необходимости."""
        try:
            s3_client = storage.connection.meta.client
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception:
            try:
                s3_client.create_bucket(Bucket=bucket_name)
                logger.info('Создан бакет %s', bucket_name)
            except Exception as err:
                logger.warning(
                    'Не удалось создать бакет %s: %s', bucket_name, err,
                )

    @classmethod
    def _generate_cloud_path(cls, media_type: MediaType, filename: str) -> str:
        """Генерирует путь к файлу в облаке: {prefix}/{uuid}.{ext}."""
        parts = filename.split('.')
        ext = parts[-1].lower() if len(parts) > 1 else 'jpg'
        return f'{media_type.value}/{uuid4().hex}.{ext}'
