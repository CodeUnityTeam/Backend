import uuid

from django.contrib.auth import get_user_model
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models

from core.constants.projects import (
    INITIATOR_RESPONSE,
    MAX_LEN_FULL_DESC,
    MAX_LEN_INITIATOR_TYPE,
    MAX_LEN_LOCATION,
    MAX_LEN_STATUS,
    MAX_LEN_STATUS_PARTICIPANT,
    MAX_LEN_STATUS_RESPONSE,
    MAX_LEN_TITLE,
    MAX_LEN_WORK_FORMAT,
    MAX_SHORT_DESC,
    MIN_LEN_TITLE,
    MIN_SHORT_DESC,
    STATUS_PARTICIPANT,
    STATUS_PROJECT,
    STATUS_RESPONSE_PROJECT,
)
from core.models.mixins import CreatedAtMixin, TimestampMixin

from .validators import validate_location

User = get_user_model()


class WorkFormat(models.Model):
    """Модель для форматов работы."""

    format_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор формата работы',
    )
    name = models.CharField(
        max_length=MAX_LEN_WORK_FORMAT,
        unique=True,
        verbose_name='Название формата работы',
        help_text='Пример: Удалённо, Гибрид, В офисе',
    )

    def __str__(self) -> str:
        return self.name

    class Meta:
        """Метаданные модели."""

        db_table = 'work_format'
        verbose_name = 'Формат работы'
        verbose_name_plural = 'Форматы работы'


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
        on_delete=models.CASCADE,
        to_field='user_id',
        related_name='projects',
        verbose_name='Автор проекта',
        null=False,
    )
    title = models.CharField(
        max_length=MAX_LEN_TITLE,
        verbose_name='Название проекта',
        validators=[
            MinLengthValidator(
                limit_value=MIN_LEN_TITLE,
                message=(
                    f'Название должно быть не короче {MIN_LEN_TITLE} символов.'
                ),
            ),
            MaxLengthValidator(
                limit_value=MAX_LEN_TITLE,
                message=(
                    f'Название не должно превышать {MAX_LEN_TITLE} символов.'
                ),
            ),
        ],
    )
    short_desc = models.CharField(
        max_length=MAX_SHORT_DESC,
        verbose_name='Краткое описание проекта',
        validators=[
            MinLengthValidator(
                limit_value=MIN_SHORT_DESC,
                message=(
                    'Краткое описание проекта должно быть не короче '
                    f'{MIN_SHORT_DESC} символов.'
                ),
            ),
            MaxLengthValidator(
                limit_value=MAX_LEN_TITLE,
                message=(
                    'Краткое описание проекта не должно превышать '
                    f'{MAX_SHORT_DESC} символов.'
                ),
            ),
        ],
    )
    full_desc = models.TextField(
        verbose_name='Полное описание проекта',
        blank=True,
        null=True,
        validators=[
            MaxLengthValidator(
                limit_value=MAX_LEN_FULL_DESC,
                message=(
                    'Полное описание не должно превышать '
                    f'{MAX_LEN_FULL_DESC} символов.'
                ),
            ),
        ],
    )
    location = models.CharField(
        max_length=MAX_LEN_LOCATION,
        verbose_name='Локация проекта',
        validators=[validate_location],
    )
    start_date = models.DateField(
        verbose_name='Дата начала проекта',
        help_text='Если не указана — подставляется текущая дата.',
        null=False,
        blank=False,
    )
    end_date = models.DateField(
        verbose_name='Дата окончания проекта',
        null=False,
        blank=False,
    )
    status_project = models.CharField(
        max_length=MAX_LEN_STATUS,
        verbose_name='Статус проекта',
        choices=STATUS_PROJECT,
        default='draft',
        help_text=(
            'draft → published: публикация.'
            'Из published в draft запрещено.'
        ),
    )
    published_at = models.DateTimeField(
        verbose_name='Дата первой публикации',
        null=True,
        blank=True,
        editable=False,
        help_text=(
            'Заполняется при первом переходе draft → published. '
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

    @property
    def participants_count(self) -> int:
        """Вычисляемое поле: количество участников.

        - включает автора и всех подтверждённых участников.
        - не включает ожидающих (pending) и отклонённых (rejected).
        """
        return self.participants.count()

    class Meta:
        """Метаданные модели."""

        db_table = 'projects'
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'

    def __str__(self) -> str:
        return f'Проект {self.project_id} - {self.title}.'


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
        db_column='user_id',
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
        unique_together = ('project', 'user')
        verbose_name = 'Участник проекта'
        verbose_name_plural = 'Участники проекта'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'user'],
                name='unique_project_participant',
            ),
        ]

    def __str__(self) -> str:
        return (
            f'Пользоваетель {self.user}.'
            f'Статус отклика {self.status_participant}.'
            f'Проект {self.project.title}.'
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
        db_column='user_id',
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
        unique_together = ('user', 'project')
        verbose_name = 'Лайк проекта'
        verbose_name_plural = 'Лайки проектов'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'project'],
                name='unique_user_project_like',
            ),
        ]
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'project']),
        ]

    def __str__(self) -> str:
        return (
            f'Лайк пользователя {self.user} на проект {self.project.title}'
        )


class Response(CreatedAtMixin, models.Model):
    """Отклик пользователя на проект или приглашение от автора.

    - Один пользователь может иметь только один отклик/приглашение на проект.
    - При одобрении создаётся запись в ProjectParticipant.
    - Поддержка инициатора: соискатель (applicant) или автор (author).
    """

    response_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор отклика',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.RESTRICT,
        db_column='project_id',
        related_name='responses',
        verbose_name='Проект',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='responses',
        verbose_name='Пользователь',
    )
    initiator_type = models.CharField(
        max_length=MAX_LEN_INITIATOR_TYPE,
        choices=INITIATOR_RESPONSE,
        verbose_name='Инициатор',
    )
    status_resp = models.CharField(
        max_length=MAX_LEN_STATUS_RESPONSE,
        choices=STATUS_RESPONSE_PROJECT,
        default='pending',
        verbose_name='Статус отклика',
    )

    class Meta:
        """Мeтаданные модели."""

        db_table = 'response'
        unique_together = ('project', 'user')
        verbose_name = 'Отклик'
        verbose_name_plural = 'Отклики'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'user'],
                name='unique_response_per_project_user',
            ),
        ]
        indexes = [
            models.Index(fields=['status_resp']),
            models.Index(fields=['initiator_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['project', 'user']),
        ]

    def __str__(self) -> str:
        return (
            f'Отклик на проект {self.project.title} пользователя {self.user}'
        )
