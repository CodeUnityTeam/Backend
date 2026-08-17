import uuid

from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models

from core.constants.feedback import (
    FEEDBACK_STATUS_SENT,
    MAX_CONTENT_FEEDBACK,
    MAX_LEN_STATUS_FEEDBACK,
    MAX_REVIEW_TEXT,
    MAX_SUBJECT_FEEDBACK,
    MIN_REVIEW_TEXT,
    STATUS_FEEDBACK,
)
from core.models.mixins import BaseImageMixin, TimestampMixin

User = get_user_model()


class Review(TimestampMixin, models.Model):
    """Отзыв пользователя о платформе.

    - Содержит текст отзыва.
    - Привязан к пользователю, который написал отзыв.
    - Один пользователь может оставить только один отзыв.
    """

    review_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор отзыва',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='reviews',
        verbose_name='Пользователь',
    )
    text = models.TextField(
        max_length=MAX_REVIEW_TEXT,
        validators=[MinLengthValidator(MIN_REVIEW_TEXT)],
        verbose_name='Текст отзыва',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'reviews'
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        constraints = (
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user_review',
                violation_error_message='Пользователь уже оставил отзыв.',
            ),
        )
        indexes = (
            models.Index(fields=['user']),
            models.Index(fields=['-created_at']),
        )

    def __str__(self) -> str:
        return (
            f'Отзыв от {self.user.first_name}: {self.text[:50]}...'
        )


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
        default=FEEDBACK_STATUS_SENT,
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
        indexes = (
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        )

    def __str__(self) -> str:
        return f'{self.subject} — {self.user.first_name} ({self.status})'


class FeedbackImage(BaseImageMixin):
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
        indexes = (
            models.Index(fields=['feedback']),
        )

    def __str__(self) -> str:
        return f'Изображение: {self.original_name} для {self.feedback.subject}'
