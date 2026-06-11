import uuid

from django.contrib import admin
from django.db import models
from django.utils.safestring import mark_safe

from core.constants.qna import MAX_IMAGE_URL, MAX_MINE_TYPE, MAX_ORIGINAL_NAME


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

    @admin.display(description="Изображение")
    def post_image(self):  # noqa: ANN201
        """Отображает превью в админке."""
        if self.image_url:
            return mark_safe(f"<img src='{self.image_url}' width=50>")
        return "Без фото"
