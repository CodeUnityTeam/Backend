from django.conf import settings
from django.db import models


class UserWorkFormat(models.Model):
    """Связь пользователя с навыком."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='user_workformat',
        verbose_name='Пользователь',
        help_text='Пользователь, которому назначен формат работы.',
    )
    workformat = models.ForeignKey(
        'projects.WorkFormat',
        on_delete=models.PROTECT,
        related_name='user_workformats',
        verbose_name='Формат работы',
        help_text='Формат работы пользователя.',
    )

    class Meta:
        db_table = 'user_workformat'
        verbose_name = 'Формат работы пользователя.'
        verbose_name_plural = 'Форматы работы пользователя.'
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'workformat'),
                name='unique_user_workformat',
            ),
        )

    def __str__(self) -> str:
        return f'{self.user} - {self.workformat}'
