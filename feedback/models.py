import uuid

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.safestring import mark_safe

from core.constants import (
    MAX_CONTENT_FEEDBACK,
    MAX_IMAGE_URL,
    MAX_LEN_STATUS_FEEDBACK,
    MAX_MINE_TYPE,
    MAX_ORIGINAL_NAME,
    MAX_SUBJECT_FEEDBACK,
    STATUS_FEEDBACK,
)
from core.models.mixins import TimestampMixin

User = get_user_model()


class FeedbackForm(TimestampMixin, models.Model):
    """Форма обратной связи, отправленная пользователем.

    - Привязана к пользователю.
    - Статус обновляется администратором.
    - Можно прикрепить изображение.
    """

    feedback_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор формы',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='feedback_forms',
        verbose_name='Пользователь',
    )
    status = models.CharField(
        max_length=MAX_LEN_STATUS_FEEDBACK,
        default='Sent',
        choices=STATUS_FEEDBACK,
        verbose_name='Статус',
    )
    subject = models.CharField(
        max_length=MAX_SUBJECT_FEEDBACK,
        verbose_name='Тема',
    )
    content = models.CharField(
        max_length=MAX_CONTENT_FEEDBACK,
        verbose_name='Содержание',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'feedback_form'
        verbose_name = 'Форма обратной связи'
        verbose_name_plural = 'Формы обратной связи'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.subject} — {self.user.first_name} ({self.status})'


class FeedbackImage(TimestampMixin, models.Model):
    """Изображение, прикреплённое к форме обратной связи.

    - Хранит метаданные и URL.
    - Привязано к форме и времени загрузки.
    """

    feedback_image = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор изображения',
    )
    feedback = models.ForeignKey(
        FeedbackForm,
        on_delete=models.CASCADE,
        db_column='feedback_id',
        related_name='images',
        verbose_name='Форма',
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
        verbose_name='MIME-тип',
    )
    image_url = models.URLField(
        max_length=MAX_IMAGE_URL,
        verbose_name='URL изображения',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'feedback_form_image'
        verbose_name = 'Изображение для обратной связи'
        verbose_name_plural = 'Изображения обратной связи'
        indexes = [
            models.Index(fields=['feedback']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f'Изображение: {self.original_name} для {self.feedback.subject}'

    @admin.display(description="Изображение")
    def post_image(self):   # noqa: ANN201
        """Отображает превью в админке."""
        if self.image_url:
            return mark_safe(f"<img src='{self.image_url}' width=50>")
        return "Без фото"
