import uuid

from django.conf import settings
from django.db import models

from core.constants.users import (
    SPECIALIZATION_NAME_LENGTH,  # стоит импортировать из пакета core
)


class Specialization(models.Model):
    """Модель специализации пользователя."""

    spec_id = models.UUIDField(
        'ID специализации',
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Уникальный идентификатор специализации.',
    )
    name = models.CharField(
        verbose_name='Название',
        max_length=SPECIALIZATION_NAME_LENGTH,
        unique=True,
        help_text='Название специализации.',
    )

    class Meta:
        db_table = 'specialization'
        verbose_name = 'специализация'
        verbose_name_plural = 'Специализации'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name


class UserSpecialization(models.Model):
    """Связь пользователя со специализацией."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_specializations',
        verbose_name='Пользователь',
        help_text='Пользователь, которому назначена специализация.',
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        related_name='user_specializations',
        verbose_name='Специализация',
        help_text='Специализация пользователя.',
    )

    class Meta:
        db_table = 'user_specialization'
        verbose_name = 'специализация пользователя'
        verbose_name_plural = 'Специализации пользователей'
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'specialization'),
                name='unique_user_specialization',
            ),
        )

    def __str__(self) -> str:
        return f'{self.user} - {self.specialization}'
