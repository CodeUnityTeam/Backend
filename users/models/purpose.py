import uuid

from django.db import models

from core.constants import MAX_PURPOSE_NAME


class Purpose(models.Model):
    """Модель для хранения целей создания токенов.

    Используется для определения типа операции, для которой выдан токен:
    - подтверждение email (регистрация);
    - сброс пароля;
    - смена email.
    """

    purpose_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Уникальный идентификатор цели создания токена',
        help_text='Формируется автоматически при создании новой записи',
    )
    name = models.CharField(
        max_length=MAX_PURPOSE_NAME,
        unique=True,
        verbose_name='Название цели создания токена',
        help_text=(
            'Допустимые значения: '
            'email_confirmation (подтверждение email), '
            'password_reset (сброс пароля), '
            'email_change (смена email)'
        ),
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'purpose'
        verbose_name = 'Цель токена'
        verbose_name_plural = 'Цели токенов'
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self) -> str:
        return self.name
