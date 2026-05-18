import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from purpose import Purpose

User = get_user_model()


class UserToken(models.Model):
    """Модель для хранения токенов подтверждения пользователя.

    Используется для:
    - подтверждения регистрации;
    - восстановления пароля;
    - смены адреса электронной почты.
    """

    token_hash = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Уникальный идентификатор токена',
        help_text='Формируется автоматически при создании новой записи',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='user_tokens',
        verbose_name='Пользователь',
        help_text='Уникальный идентификатор записи по пользователю',
    )
    purpose = models.ForeignKey(
        Purpose,
        on_delete=models.CASCADE,
        db_column='purpose_id',
        related_name='tokens',
        verbose_name='Цель токена',
        help_text='Уникальный идентификатор цели создания токена',
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата и время создания токена',
        help_text='Текущая дата и время по МСК',
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время использования токена',
        help_text='Заполняется автоматически при использовании токена',
    )
    expires_at = models.DateTimeField(
        verbose_name='Дата и время истечения срока действия токена',
        help_text=(
            'Формируется автоматически. '
            'Текущая дата и время по МСК + срок действия'
        ),
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'user_token'
        verbose_name = 'Токен подтверждения'
        verbose_name_plural = 'Токены подтверждения'
        indexes = [
            models.Index(fields=['user', 'purpose']),
        ]

    def __str__(self) -> str:
        return f'Токен для {self.user.email}'

    @property
    def is_expired(self) -> bool:
        """Проверяет, истёк ли срок действия токена."""
        return timezone.now() > self.expires_at

    @property
    def is_used(self) -> bool:
        """Проверяет, был ли токен использован."""
        return self.used_at is not None

    def mark_as_used(self) -> None:
        """Помечает токен как использованный."""
        if not self.is_used:
            self.used_at = timezone.now()
            self.save(update_fields=['used_at'])
