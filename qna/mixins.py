import uuid

from django.contrib.auth.models import User
from django.db import models

from core.constants import MAX_IMAGE_URL, MAX_MINE_TYPE, MAX_ORIGINAL_NAME


class BaseImageMixin(models.Model):
    """Базовый класс для изображений в вопросах и ответах."""

    image_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор изображения',
    )
    original_name = models.CharField(
        max_length=MAX_ORIGINAL_NAME,
        verbose_name='Оригинальное имя файла',
    )
    file_size = models.IntegerField(
        verbose_name='Размер файла в байтах',
    )
    mime_type = models.CharField(
        max_length=MAX_MINE_TYPE,
        verbose_name='Тип файла',
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время загрузки',
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='uploaded_by',
        verbose_name='Загружено',
    )
    image_url = models.URLField(
        max_length=MAX_IMAGE_URL,
        verbose_name='URL изображения',
    )

    class Meta:
        """Метаданные модели."""

        abstract = True
