import json
from typing import Any

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from storages.backends.s3boto3 import S3Boto3Storage


class MinioService:
    """Транспортный сервис для управления файлами в MinIO/S3."""

    def __init__(self, bucket_name: str) -> None:
        """Инициализировать имя бакета и настройки хранилища."""
        self.bucket_name: str = bucket_name
        self.storage: S3Boto3Storage = self._init_storage()
        self._ensure_bucket_templated()

    def _init_storage(self) -> S3Boto3Storage:
        """Внутренний метод инициализации S3-хранилища."""
        options: dict[str, Any] = settings.S3_OPTIONS
        endpoint_url: str = options.get('endpoint_url', '')

        clean_domain: str = endpoint_url.replace(
            'http://', '',
        ).replace('https://', '')
        custom_domain: str = f'{clean_domain}/{self.bucket_name}'

        return S3Boto3Storage(
            access_key=options.get('access_key'),
            secret_key=options.get('secret_key'),
            bucket_name=self.bucket_name,
            endpoint_url=endpoint_url,
            custom_domain=custom_domain,
            querystring_auth=False,
            file_overwrite=False,
        )

    def _ensure_bucket_templated(self) -> None:
        """Проверить наличие бакета и сделать его публичным на чтение."""
        try:
            s3_client: Any = self.storage.connection.meta.client

            # 1. Проверяем существование бакета. Если нет — создаем.
            try:
                s3_client.head_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == '404':
                    s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    raise e

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
        except Exception:  # noqa: BLE001
            pass

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
        except Exception:  # noqa: BLE001
            pass
