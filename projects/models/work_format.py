import uuid

from django.db import models

from core.constants.projects import MAX_LEN_WORK_FORMAT


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
