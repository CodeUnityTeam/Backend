import uuid

from django.conf import settings
from django.db import models

from core.constants.users import SKILL_NAME_LENGTH


class Skill(models.Model):
    """Модель навыка пользователя."""

    skill_id = models.UUIDField(
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
        db_table = 'skills'
        verbose_name = 'навык'
        verbose_name_plural = 'Навыки'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name


class UserSkill(models.Model):
    """Связь пользователя с навыком."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='user_skills',
        verbose_name='Пользователь',
        help_text='Пользователь, которому назначен навык.',
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name='user_skills',
        verbose_name='Навык',
        help_text='Навык пользователя.',
    )

    class Meta:
        db_table = 'user_skills'
        verbose_name = 'навык пользователя'
        verbose_name_plural = 'Навыки пользователей'
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'skill'),
                name='unique_user_skill',
            ),
        )

    def __str__(self) -> str:
        return f'{self.user} - {self.skill}'
