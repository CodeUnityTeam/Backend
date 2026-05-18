import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.constants import (
    MAX_EMAIL_LENGTH,
    MAX_FIRST_NAME_LENGTH,
    MAX_IMAGE_URL,
    MAX_LAST_NAME_LENGTH,
    MAX_PURPOSE_NAME,
    MAX_ROLE_LENGTH,
    MAX_USERNAME_LENGTH,
    OAUTHPROVIDER_NAME_LENGTH,
    ROLE_ADMIN,
    ROLE_CHOICES_LIST,
    ROLE_MODERATOR,
    ROLE_USER,
    SKILL_NAME_LENGTH,
    SPECIALIZATION_NAME_LENGTH,
)


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


class Purpose(models.Model):
    """Модель для хранения целей создания токенов.

    Используется для определения типа операции, для которой выдан токен:
    - подтверждение email (регистрация);
    - сброс пароля;
    - смена email.
    """

    purpose_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Уникальный идентификатор цели создания токена',
        help_text='Формируется автоматически при создании новой записи',
    )
    name = models.CharField(
        max_length=MAX_PURPOSE_NAME,
        unique=True,
        verbose_name='Название цели создания токена',
        help_text=(
            'Допустимые значения: '
            'email_confirmation (подтверждение email), '
            'password_reset (сброс пароля), '
            'email_change (смена email)'
        ),
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'purpose'
        verbose_name = 'Цель токена'
        verbose_name_plural = 'Цели токенов'
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self) -> str:
        return self.name


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


class Specialization(models.Model):
    """Модель специализации пользователя."""

    spec = models.UUIDField(
        'ID специализации',
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Уникальный идентификатор специализации.',
    )
    name = models.CharField(
        verbose_name='Название',
        max_length=SPECIALIZATION_NAME_LENGTH,
        unique=True,
        help_text='Название специализации.',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'specialization'
        verbose_name = 'Специализация'
        verbose_name_plural = 'Специализации'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
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
    avatar = models.URLField(
        null=True,
        blank=True,
        max_length=MAX_IMAGE_URL,
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
        help_text='Навыки пользователя',
    )
    specialization = models.ManyToManyField(
        Specialization,
        db_table='user_specializations',
        verbose_name='Специализации пользователя',
        related_name='users',
        blank=True,
        help_text='Специализации пользователя',
    )
    user_format = models.ManyToManyField(
        'projects.WorkFormat',
        db_table='user_formats',
        verbose_name='Формат работы пользователя',
        related_name='users',
        blank=True,
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


class UserToken(models.Model):
    """Модель для хранения токенов подтверждения пользователя.

    Используется для:
    - подтверждения регистрации;
    - восстановления пароля;
    - смены адреса электронной почты.
    """

    token_hash = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Уникальный идентификатор токена',
        help_text='Формируется автоматически при создании новой записи',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='user_tokens',
        verbose_name='Пользователь',
        help_text='Уникальный идентификатор записи по пользователю',
    )
    purpose = models.ForeignKey(
        Purpose,
        on_delete=models.CASCADE,
        db_column='purpose_id',
        related_name='tokens',
        verbose_name='Цель токена',
        help_text='Уникальный идентификатор цели создания токена',
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата и время создания токена',
        help_text='Текущая дата и время по МСК',
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время использования токена',
        help_text='Заполняется автоматически при использовании токена',
    )
    expires_at = models.DateTimeField(
        verbose_name='Дата и время истечения срока действия токена',
        help_text=(
            'Формируется автоматически. '
            'Текущая дата и время по МСК + срок действия'
        ),
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'user_token'
        verbose_name = 'Токен подтверждения'
        verbose_name_plural = 'Токены подтверждения'
        indexes = [
            models.Index(fields=['user', 'purpose']),
        ]

    def __str__(self) -> str:
        return f'Токен для {self.user.email}'

    @property
    def is_expired(self) -> bool:
        """Проверяет, истёк ли срок действия токена."""
        return timezone.now() > self.expires_at

    @property
    def is_used(self) -> bool:
        """Проверяет, был ли токен использован."""
        return self.used_at is not None

    def mark_as_used(self) -> None:
        """Помечает токен как использованный."""
        if not self.is_used:
            self.used_at = timezone.now()
            self.save(update_fields=['used_at'])
