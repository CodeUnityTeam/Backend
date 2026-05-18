import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.constants import (
    MAX_EMAIL_LENGTH,
    MAX_FIRST_NAME_LENGTH,
    MAX_LAST_NAME_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_USERNAME_LENGTH,
    ROLE_ADMIN,
    ROLE_CHOICES_LIST,
    ROLE_MODERATOR,
    ROLE_USER,
)
from projects.models import WorkFormat

from .providers import OauthProvider
from .skills import Skill
from .specializations import Specialization


class CastomUser(AbstractUser):
    """Модель пользователя."""

    user_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Уникальный идентификатор пользователя',
    )
    email = models.EmailField(
        max_length=MAX_EMAIL_LENGTH,
        unique=True,
        verbose_name='электронная почта',
    )
    provider = models.ForeignKey(
        OauthProvider,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='OAuth-провайдер',
        help_text='OAuth-провайдер пользователя.',
    )
    username = models.CharField(
        blank=False,
        null=False,
        unique=True,
        max_length=MAX_USERNAME_LENGTH,
        verbose_name='имя(никнейм)',
    )
    first_name = models.CharField(
        max_length=MAX_FIRST_NAME_LENGTH,
        verbose_name='Имя',
    )
    last_name = models.CharField(
        max_length=MAX_LAST_NAME_LENGTH,
        verbose_name='Фамилия',
    )
    avatar = models.ImageField(
        default=None,
        blank=True,
        null=True,
        upload_to='media/users/',
        verbose_name='аватар профиля',
        help_text='аватар профиля',
    )
    role = models.CharField(
        verbose_name='роль',
        max_length=MAX_ROLE_LENGTH,
        choices=ROLE_CHOICES_LIST,
        default=ROLE_USER,
        blank=False,
    )
    is_active = models.BooleanField(
        verbose_name='Флаг активности',
        default=True,
        help_text='Отмечает активного пользователя.',
    )
    date_joined = models.DateTimeField(
        verbose_name='Дата регистрации',
        default=timezone.now,
        help_text='Дата и время регистрации пользователя.',
    )
    is_agreed_to_terms = models.BooleanField(
        verbose_name='Согласие обработку данных',
        default=False,
        help_text='Пользователь согласился с условиями использования.',
    )
    skills = models.ManyToManyField(
        Skill,
        db_table='user_skills',
        verbose_name='Навыки пользователя',
        related_name='users',
        blank=True,
        null=True,
        help_text='Навыки пользователя',
    )
    specialization = models.ManyToManyField(
        Specialization,
        db_table='user_specializations',
        verbose_name='Специализации пользователя',
        related_name='users',
        blank=True,
        null=True,
        help_text='Специализации пользователя',
    )
    user_format = models.ManyToManyField(
        WorkFormat,
        db_table='user_formats',
        verbose_name='Формат работы пользователя',
        related_name='users',
        blank=True,
        null=True,
        help_text='Формат работы пользователя',
    )

    @property
    def is_admin(self) -> bool:
        """Проверка на админа."""
        return self.role == ROLE_ADMIN

    @property
    def is_moderator(self) -> bool:
        """Проверка на модератора."""
        return self.role == ROLE_MODERATOR
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ('username', 'first_name', 'last_name')

    class Meta:
        """Метаданные модели."""

        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
        return f'Пользователь {self.user_id} с мылом {self.email}'
