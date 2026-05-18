import uuid

from django.db import models

from core.constants import OAUTHPROVIDER_NAME_LENGTH


class OauthProvider(models.Model):
    """Модель OAuth-провайдера."""

    provider_id = models.UUIDField(
        'ID провайдера',
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Уникальный идентификатор провайдера.',
    )
    name = models.CharField(
        verbose_name='Название',
        max_length=OAUTHPROVIDER_NAME_LENGTH,
        unique=True,
        help_text='Название провайдера.',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'oauth_provider'
        verbose_name = 'OAuth-провайдер'
        verbose_name_plural = 'OAuth-провайдеры'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name
