"""
Management command для очистки "сиротских" файлов из S3/MinIO.

Файлы считаются сиротами, если они загружены в S3, но не привязаны
ни к одной записи в БД. Это может происходить, когда пользователь
загрузил файл через /api/v1/qna/files/upload/, но не завершил
создание вопроса/ответа.

Использование:
    python manage.py cleanup_s3_orphans --dry-run
    python manage.py cleanup_s3_orphans --force
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand

from core.s3_utils import S3Service, MediaType
from feedback.models import FeedbackImage
from qna.models import AnswerImage, QuestionImage
from users.models import User

logger = logging.getLogger(__name__)

# Маппинг: MediaType -> (QuerySet с URL, имя поля с URL)
REGISTERED_MODELS = (
    (QuestionImage, 'image_url'),
    (AnswerImage, 'image_url'),
    (FeedbackImage, 'image_url'),
    (User, 'avatar_url'),
)


class Command(BaseCommand):
    """Очищает сиротские файлы из S3."""

    help = (
        'Находит и удаляет файлы в S3, которые не привязаны '
        'ни к одной записи в БД.'
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Режим "сухого прогона": только показать, что будет удалено.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help='Режим принудительного удаления без подтверждения.',
        )

    def _get_registered_urls(self) -> set[str]:
        """Собирает все URL изображений, привязанных к записям в БД."""
        registered: set[str] = set()
        for model_cls, field_name in REGISTERED_MODELS:
            urls = model_cls.objects.exclude(
                **{f'{field_name}__isnull': True},
            ).exclude(
                **{f'{field_name}__exact': ''},
            ).values_list(field_name, flat=True)
            registered.update(urls)
        return registered

    def _list_s3_objects(
        self, media_type: MediaType,
    ) -> list[dict[str, Any]]:
        """Получает список всех объектов в бакете через S3 API."""
        storage = S3Service._get_storage(media_type)  # noqa: SLF001
        s3_client = storage.connection.meta.client
        bucket_name = S3Service._get_bucket_name(media_type)  # noqa: SLF001
        objects: list[dict[str, Any]] = []
        paginator = s3_client.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                objects.extend(page['Contents'])
        return objects

    def _delete_s3_object(
        self, media_type: MediaType, object_key: str,
    ) -> None:
        """Удаляет объект из S3 по его ключу."""
        storage = S3Service._get_storage(media_type)  # noqa: SLF001
        s3_client = storage.connection.meta.client
        bucket_name = S3Service._get_bucket_name(media_type)  # noqa: SLF001
        s3_client.delete_object(
            Bucket=bucket_name,
            Key=object_key,
        )

    def _get_object_url(
        self, media_type: MediaType, object_key: str,
    ) -> str:
        """Формирует публичный URL объекта, как он хранится в БД."""
        storage = S3Service._get_storage(media_type)  # noqa: SLF001
        return storage.url(object_key)

    def handle(self, *args: Any, **options: Any) -> str | None:  # noqa: ARG002
        dry_run: bool = options['dry_run']
        force: bool = options['force']

        self.stdout.write('Собираю URL, зарегистрированные в БД...')
        registered_urls = self._get_registered_urls()
        self.stdout.write(f'  Найдено {len(registered_urls)} URL в БД.')

        total_orphans = 0
        for media_type in MediaType:
            bucket_name = S3Service._get_bucket_name(media_type)  # noqa: SLF001
            prefix = media_type.value

            self.stdout.write(
                f'Сканирую бакет "{bucket_name}" (префикс "{prefix}")...',
            )

            try:
                s3_objects = self._list_s3_objects(media_type)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Ошибка доступа к бакету "{bucket_name}": {e}',
                    ),
                )
                continue

            # Фильтруем объекты по префиксу
            prefix_objects = [
                obj for obj in s3_objects
                if obj['Key'].startswith(f'{prefix}/')
            ]

            for obj in prefix_objects:
                object_key: str = obj['Key']
                object_url = self._get_object_url(media_type, object_key)

                if object_url not in registered_urls:
                    total_orphans += 1
                    size_mb = obj.get('Size', 0) / (1024 * 1024)
                    self.stdout.write(
                        f'  Сирота: {object_key} '
                        f'({size_mb:.2f} MB)',
                    )

                    if not dry_run and force:
                        try:
                            self._delete_s3_object(media_type, object_key)
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'    ✓ Удалён',
                                ),
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'    ✗ Ошибка удаления: {e}',
                                ),
                            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nРежим DRY-RUN. Найдено {total_orphans} сирот. '
                    'Запустите с --force для удаления.',
                ),
            )
        elif not force:
            self.stdout.write(
                self.style.WARNING(
                    f'\nНайдено {total_orphans} сирот. '
                    'Используйте --force для фактического удаления.',
                ),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nГотово. Удалено {total_orphans} сиротских файлов.',
                ),
            )

        return None