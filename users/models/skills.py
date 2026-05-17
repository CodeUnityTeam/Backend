import uuid

from django.db import models

from core.constants import SKILL_NAME_LENGTH


class Skill(models.Model):
    """Модель навыка пользователя."""

    skill = models.UUIDField(
        'ID навыка',
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Уникальный идентификатор навыка.',
    )
    name = models.CharField(
        verbose_name='Название',
        max_length=SKILL_NAME_LENGTH,
        unique=True,
        help_text='Название навыка.',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'skills'
        verbose_name = 'Навык'
        verbose_name_plural = 'Навыки'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name
