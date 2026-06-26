import uuid

from django.db import models

from core.constants.projects import (
    INITIATOR_RESPONSE,
    MAX_LEN_INITIATOR_TYPE,
    MAX_LEN_STATUS_RESPONSE,
    STATUS_RESPONSE_PROJECT,
)
from core.models.mixins import CreatedAtMixin

from .project import Project


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
        verbose_name = 'Отклик'
        verbose_name_plural = 'Отклики'
        constraints = (
            models.UniqueConstraint(
                fields=['project', 'user'],
                name='unique_response_per_project_user',
            ),
        )
        indexes = (
            models.Index(fields=['status_resp']),
            models.Index(fields=['created_at']),
        )

    def __str__(self) -> str:
        return (
            f'Отклик на проект {self.project.title} пользователя {self.user}'
        )
