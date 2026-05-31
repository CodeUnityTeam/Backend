import uuid

from django.contrib.auth.models import (
    AbstractUser,
)
from django.core.validators import (
    RegexValidator,
)
from django.db import models
from django.db.models import Q

from core.constants.users import (
    MAX_PHONE_DIGITS,
    MIN_PHONE_DIGITS,
    PHONE_PATTERN,
    USER_ADDITIONAL_CONTACT_LENGTH,
    USER_CITY_LENGTH,
    USER_COUNTRY_LENGTH,
    USER_EMAIL_HELP,
    USER_EMAIL_LENGTH,
    USER_FIRST_NAME_LENGTH,
    USER_LAST_NAME_LENGTH,
    USER_NAME_HELP,
    USER_NAME_PATTERN,
    USER_ROLE_LENGTH,
)
from core.models.mixins import TimestampMixin


class User(TimestampMixin, AbstractUser):
    """Кастомная модель пользователя на базе стандартного AbstractUser."""

    class RoleChoices(models.TextChoices):
        USER = 'user', 'Пользователь'
        MODERATOR = 'moderator', 'Модератор'
        ADMIN = 'admin', 'Администратор'

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    user_id = models.UUIDField(
        'ID пользователя',
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Уникальный идентификатор.',
    )
    role = models.CharField(
        'Роль',
        max_length=USER_ROLE_LENGTH,
        choices=RoleChoices.choices,
        default=RoleChoices.USER,
        help_text='Роль пользователя в системе.',
    )
    email = models.EmailField(
        'Электронная почта',
        max_length=USER_EMAIL_LENGTH,
        help_text=USER_EMAIL_HELP,
        unique=True,
    )
    is_email_confirmed = models.BooleanField(
        'Email подтверждён',
        default=False,
        help_text='Отмечает, подтверждён ли основной email пользователя.',
    )
    new_email = models.EmailField(
        'Новая электронная почта',
        max_length=USER_EMAIL_LENGTH,
        help_text=USER_EMAIL_HELP,
        blank=True,
        default='',
    )
    is_password_confirmed = models.BooleanField(
        'Пароль подтверждён',
        default=False,
        help_text='Отмечает, подтверждён ли пароль пользователя.',
    )
    is_agreed_to_terms = models.BooleanField(
        'Согласие с условиями',
        default=False,
        help_text='Пользователь согласился с условиями использования.',
    )
    first_name = models.CharField(
        'Имя',
        max_length=USER_FIRST_NAME_LENGTH,
        validators=[
            RegexValidator(
                regex=USER_NAME_PATTERN,
                message=USER_NAME_HELP,
            ),
        ],
    )
    last_name = models.CharField(
        'Фамилия',
        max_length=USER_LAST_NAME_LENGTH,
        validators=[
            RegexValidator(
                regex=USER_NAME_PATTERN,
                message=USER_NAME_HELP,
            ),
        ],
    )
    phone_number = models.CharField(
        'Номер телефона',
        max_length=MAX_PHONE_DIGITS,
        blank=True,
        default='',
        validators=[
            RegexValidator(
                regex=PHONE_PATTERN,
                message=(
                    'Телефон должен начинаться с + и содержать от '
                    f'{MIN_PHONE_DIGITS} до {MAX_PHONE_DIGITS} цифр.'
                ),
            ),
        ],
    )
    additional_contact = models.CharField(
        'Дополнительный контакт',
        max_length=USER_ADDITIONAL_CONTACT_LENGTH,
        blank=True,
        default='',
    )
    country = models.CharField(
        'Страна',
        max_length=USER_COUNTRY_LENGTH,
        blank=True,
        default='',
    )
    city = models.CharField(
        'Город',
        max_length=USER_CITY_LENGTH,
        blank=True,
        default='',
    )
    about_me = models.TextField(
        'Описание',
        blank=True,
        default='',
    )
    avatar_url = models.URLField(
        'URL аватара',
        blank=True,
        default='',
    )
    specializations = models.ManyToManyField(
        'Specialization',
        through='UserSpecialization',
        related_name='users',
        verbose_name='Специализации',
        blank=True,
    )
    skills = models.ManyToManyField(
        'Skill',
        through='UserSkill',
        related_name='users',
        verbose_name='Навыки',
        blank=True,
    )

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('-created_at',)
        constraints = (
            models.UniqueConstraint(
                fields=('new_email',),
                condition=~Q(new_email=''),
                name='unique_not_empty_new_email',
            ),
        )

    @property
    def id(self) -> str:
        """При логине ожидается id - > возвращаем user_id."""
        return self.user_id

    def __str__(self) -> str:
        return self.email
