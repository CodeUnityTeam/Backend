import uuid
from datetime import date
from typing import Any

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models

from core.constants.projects import (
    MAX_LEN_FULL_DESC,
    MAX_LEN_LOCATION,
    MAX_LEN_STATUS,
    MAX_LEN_STATUS_PARTICIPANT,
    MAX_LEN_TELEGRAM,
    MAX_LEN_TITLE,
    MAX_SHORT_DESC,
    MIN_LEN_TITLE,
    MIN_SHORT_DESC,
    STATUS_PARTICIPANT,
    STATUS_PROJECT,
)
from core.models.mixins import CreatedAtMixin, TimestampMixin

from .work_format import WorkFormat

User = settings.AUTH_USER_MODEL


class Project(TimestampMixin, models.Model):
    """Модель проекта."""

    project_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор проекта',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        to_field='user_id',
        related_name='projects',
        verbose_name='Автор проекта',
        null=False,
    )
    title = models.CharField(
        max_length=MAX_LEN_TITLE,
        validators=[MinLengthValidator(MIN_LEN_TITLE)],
        verbose_name='Название проекта',
    )
    short_desc = models.CharField(
        max_length=MAX_SHORT_DESC,
        validators=[MinLengthValidator(MIN_SHORT_DESC)],
        verbose_name='Краткое описание проекта',
    )
    full_desc = models.TextField(
        max_length=MAX_LEN_FULL_DESC,
        verbose_name='Полное описание проекта',
    )
    location = models.CharField(
        max_length=MAX_LEN_LOCATION,
        verbose_name='Местоположение',
        blank=False,
        null=False,
    )
    telegram_contact = models.CharField(
        max_length=MAX_LEN_TELEGRAM,
        verbose_name='Telegram для связи',
        help_text='Имя пользователя Telegram (например, @username)',
        blank=True,
        default='',
    )
    start_date = models.DateField(
        default=date.today,
        help_text='Если не указана - подставляется текущая дата.',
        blank=True,
        verbose_name='Дата начала проекта',
    )
    end_date = models.DateField(
        verbose_name='Дата окончания проекта',
    )
    status_project = models.CharField(
        max_length=MAX_LEN_STATUS,
        verbose_name='Статус проекта',
        choices=STATUS_PROJECT,
        default='draft',
    )
    published_at = models.DateTimeField(
        verbose_name='Дата первой публикации',
        null=True,
        blank=True,
        editable=False,
        help_text=(
            'Заполняется при первом переходе черновик → опубликовано. '
            'Не меняется при републикации.'
        ),
    )
    skills = models.ManyToManyField(
        'users.Skill',
        related_name='projects',
        db_table='project_skills',
        verbose_name='Навыки для проекта',
    )
    project_format = models.ManyToManyField(
        WorkFormat,
        related_name='projects',
        db_table='project_formats',
        verbose_name='Формат работы',
    )
    specializations = models.ManyToManyField(
        'users.Specialization',
        related_name='projects',
        db_table='project_specializations',
        verbose_name='Специализации (роли в проекте)',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'projects'
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'

        ordering = ('-published_at',)
        constraints = (
            models.UniqueConstraint(
                fields=['author', 'title'],
                name='uniq_project_title_for_author',
            ),
        )

    def __str__(self) -> str:
        return f'Проект {self.project_id} - {self.title}.'

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Тримминг пробелов в названии проектов."""
        if self.title:
            self.title = self.title.strip()
        super().save(*args, **kwargs)


class ProjectParticipant(models.Model):
    """Модель участников проекта."""

    project = models.ForeignKey(
        Project,
        on_delete=models.RESTRICT,
        db_column='project_id',
        related_name='participants',
        verbose_name='Проект',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='project_participations',
        verbose_name='Пользователь',
    )
    status_participant = models.CharField(
        max_length=MAX_LEN_STATUS_PARTICIPANT,
        choices=STATUS_PARTICIPANT,
        verbose_name='Статус участника',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'project_participant'
        verbose_name = 'Участник проекта'
        verbose_name_plural = 'Участники проекта'
        constraints = (
            models.UniqueConstraint(
                fields=['project', 'user'],
                name='unique_project_participant',
            ),
        )

    def __str__(self) -> str:
        return (
            f'Проект {self.project.title}.'
            f'Пользователь {self.user}.'
            f'Статус отклика {self.status_participant}.'
        )


class ProjectLike(CreatedAtMixin, models.Model):
    """Лайки, поставленные пользователями проектам.

    - Один пользователь может поставить лайк проекту только один раз.
    - Нельзя лайкнуть свой проект.
    - Можно лайкать только проекты со статусом 'published' или
      'recruiting_closed'.
    - При повторном нажатии — лайк удаляется (toggle-поведение).
    """

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='project_likes',
        verbose_name='Пользователь',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.RESTRICT,
        db_column='project_id',
        related_name='likes',
        verbose_name='Проект',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'project_likes'
        verbose_name = 'Лайк проекта'
        verbose_name_plural = 'Лайки проектов'
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'project'],
                name='unique_user_project_like',
            ),
        )
        indexes = (
            models.Index(fields=['created_at']),
        )

    def __str__(self) -> str:
        return f'Лайк пользователя {self.user} на проект {self.project.title}'


class ProjectFavorite(CreatedAtMixin, models.Model):
    """Избранное: проекты, добавленные пользователем в избранное.

    - Один пользователь может добавить проект в избранное только один раз.
    - Нельзя добавить в избранное свой проект.
    - Можно добавлять в избранное только проекты со статусом 'published' или
      'recruiting_closed'.
    - При повторном нажатии — запись удаляется (toggle-поведение).
    """

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='project_favorites',
        verbose_name='Пользователь',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.RESTRICT,
        db_column='project_id',
        related_name='favorites',
        verbose_name='Проект',
    )

    class Meta:
        db_table = 'project_favorites'
        verbose_name = 'Избранное проекта'
        verbose_name_plural = 'Избранное проектов'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'project'],
                name='unique_user_project_favorite',
            ),
        ]

    def __str__(self) -> str:
        return (
            f'Избранное: пользователь '
            f'{self.user} добавил проект "{self.project.title}"'
        )
