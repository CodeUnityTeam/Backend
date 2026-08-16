
from django.contrib import admin
from django.db import models
from django.utils.safestring import mark_safe

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


class BaseImageMixin(models.Model):
    """Базовый класс для изображений в вопросах, ответах и обратной связи."""

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
    image_url = models.URLField(
        max_length=MAX_IMAGE_URL,
        verbose_name='URL изображения',
    )

    class Meta:
        abstract = True

    @admin.display(description='Изображение')
    def post_image(self):  # noqa: ANN201
        """Отображает превью в админке."""
        if self.image_url:
            return mark_safe(f"<img src='{self.image_url}' width=50>")
        return 'Без фото'
