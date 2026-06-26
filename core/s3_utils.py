import json
import logging
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from storages.backends.s3boto3 import S3Boto3Storage


class S3ClientError(Exception):
    """Кастомное исключение для ошибок S3-клиента."""


class MinioService:
    """Транспортный сервис для управления файлами в MinIO/S3."""

    def __init__(self, bucket_name: str) -> None:
        """Инициализировать имя бакета и настройки хранилища."""
        self.bucket_name: str = bucket_name
        self.storage: S3Boto3Storage = self._init_storage()
        self._bucket_configured: bool = False
        self._ensure_bucket_templated()

    def _init_storage(self) -> S3Boto3Storage:
        """Внутренний метод инициализации S3-хранилища."""
        options: dict[str, Any] = settings.STORAGES['avatars']['OPTIONS']
        endpoint_url: str = options.get('endpoint_url', '')

        clean_domain: str = endpoint_url.replace(
            'http://', '',
        ).replace('https://', '')
        custom_domain: str = f'{clean_domain}/{self.bucket_name}'

        storage = S3Boto3Storage(
            access_key=options.get('access_key'),
            secret_key=options.get('secret_key'),
            bucket_name=self.bucket_name,
            endpoint_url=endpoint_url,
            custom_domain=custom_domain,
            querystring_auth=False,
            file_overwrite=False,
        )

        # Добавляем Cache-Control для иммутабельных файлов.
        # Все файлы имеют UUID в имени, поэтому новый файл = новый URL.
        # Это позволяет браузеру кэшировать их навсегда.
        storage.object_parameters['CacheControl'] = (
            'public, max-age=31536000, immutable'
        )

        return storage

    def _ensure_bucket_templated(self) -> None:
        """Проверить наличие бакета и сделать его публичным на чтение."""
        if self._bucket_configured:
            return

        try:
            s3_client: Any = self.storage.connection.meta.client

            # 1. Проверяем существование бакета. Если нет — создаем.
            try:
                s3_client.head_bucket(Bucket=self.bucket_name)
            except Exception as e:
                error_code = getattr(e, 'response', {},
                                     ).get('Error', {}).get('Code', '')
                if error_code == '404':
                    s3_client.create_bucket(Bucket=self.bucket_name)
                elif isinstance(e, S3ClientError):
                    raise e
                else:
                    raise S3ClientError(str(e)) from e

            # 2. Формируем политику анонимного чтения файлов
            public_read_policy = {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Sid': 'PublicReadGetObject',
                        'Effect': 'Allow',
                        'Principal': '*',
                        'Action': ['s3:GetObject'],
                        'Resource': [f'arn:aws:s3:::{self.bucket_name}/*'],
                    },
                ],
            }

            # 3. Применяем политику к бакету
            s3_client.put_bucket_policy(
                Bucket=self.bucket_name,
                Policy=json.dumps(public_read_policy),
            )

            # 4. Устанавливаем флаг, что бакет настроен
            self._bucket_configured = True

        except Exception as err:
            logger = logging.getLogger(__name__)
            logger.error(f'Ошибка настройки бакета {self.bucket_name}: {err}')

    def upload_file(self, cloud_path: str, file_obj: UploadedFile) -> str:
        """Загружает файл и возвращает его полный публичный URL."""
        saved_name: str = self.storage.save(cloud_path, file_obj)
        return f'http://{self.storage.custom_domain}/{saved_name}'

    def delete_file(self, file_url: str) -> None:
        """Удаляет файл из бакета по его полному URL."""
        try:
            bucket_part: str = f'{self.storage.custom_domain}/'

            if bucket_part in file_url:
                file_path: str = file_url.split(bucket_part)[-1]
                self.storage.delete(file_path)
        except Exception as err:
            logger = logging.getLogger(__name__)
            logger.error(f'Ошибка удаления файла {file_url}: {err}')
