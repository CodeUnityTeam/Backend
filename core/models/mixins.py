from django.db import models


class CreatedAtMixin(models.Model):
    """Миксин для хранения даты и времени создания записи."""

    created_at = models.DateTimeField(
        'Создано',
        auto_now_add=True,
        help_text='Дата и время создания записи.',
    )

    class Meta:
        abstract = True
        ordering = ('-created_at',)
        default_related_name = '%(app_label)s_%(class)s'


class UpdatedAtMixin(models.Model):
    """Миксин для хранения даты и времени обновления записи."""

    updated_at = models.DateTimeField(
        'Обновлено',
        auto_now=True,
        help_text='Дата и время последнего изменения записи.',
    )

    class Meta:
        abstract = True
        ordering = ('-updated_at',)
        default_related_name = '%(app_label)s_%(class)s'


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """Миксин с полями создания и обновления записи."""

    class Meta(CreatedAtMixin.Meta, UpdatedAtMixin.Meta):
        abstract = True
        ordering = ('-updated_at', '-created_at')
