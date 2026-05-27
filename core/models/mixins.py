import uuid

from django.db import models

from core.constants.qna import MAX_IMAGE_URL, MAX_MINE_TYPE, MAX_ORIGINAL_NAME


class CreatedAtMixin(models.Model):
    """Миксин для хранения даты и времени создания записи."""

    created_at = models.DateTimeField(
        'Создано',
        auto_now_add=True,
        help_text='Дата и время создания записи.',
    )

    class Meta:
        abstract = True
        ordering = ('-created_at',)
        default_related_name = '%(app_label)s_%(class)s'


class UpdatedAtMixin(models.Model):
    """Миксин для хранения даты и времени обновления записи."""

    updated_at = models.DateTimeField(
        'Обновлено',
        auto_now=True,
        help_text='Дата и время последнего изменения записи.',
    )

    class Meta:
        abstract = True
        ordering = ('-updated_at',)
        default_related_name = '%(app_label)s_%(class)s'


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """Миксин с полями создания и обновления записи."""

    class Meta(CreatedAtMixin.Meta, UpdatedAtMixin.Meta):
        abstract = True
        ordering = ('-updated_at', '-created_at')


class BaseImageMixin(CreatedAtMixin):
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
    uploaded_by = models.ForeignKey(
        'users.User',
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
