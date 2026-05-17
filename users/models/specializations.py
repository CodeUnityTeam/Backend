import uuid

from django.db import models

from core.constants import SPECIALIZATION_NAME_LENGTH


class Specialization(models.Model):
    """Модель специализации пользователя."""

    spec = models.UUIDField(
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
        """Метаданные модели."""

        db_table = 'specialization'
        verbose_name = 'Специализация'
        verbose_name_plural = 'Специализации'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name
