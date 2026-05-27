import uuid

from django.contrib.auth import get_user_model
from django.db import models

from core.constants.feedback import (
    MAX_CONTENT_FEEDBACK,
    MAX_LEN_STATUS_FEEDBACK,
    MAX_SUBJECT_FEEDBACK,
    STATUS_FEEDBACK,
)
from core.models.mixins import BaseImageMixin, TimestampMixin

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
        ]

    def __str__(self) -> str:
        return f'{self.subject} — {self.user.first_name} ({self.status})'


class FeedbackImage(BaseImageMixin, models.Model):
    """Изображение, прикреплённое к форме обратной связи.

    - Хранит метаданные и URL.
    - Привязано к форме и времени загрузки.
    """

    feedback = models.ForeignKey(
        FeedbackForm,
        on_delete=models.CASCADE,
        db_column='feedback_id',
        related_name='images',
        verbose_name='Форма',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'feedback_form_image'
        verbose_name = 'Изображение для обратной связи'
        verbose_name_plural = 'Изображения обратной связи'
        indexes = [
            models.Index(fields=['feedback']),
        ]

    def __str__(self) -> str:
        return f'Изображение: {self.original_name} для {self.feedback.subject}'
