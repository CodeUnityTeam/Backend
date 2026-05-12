import uuid

from core.constants.users import (
    ADMIN_GROUP_NAME,
    MAX_PHONE_DIGITS,
    MIN_PHONE_DIGITS,
    PHONE_PATTERN,
    USER_ADDITIONAL_CONTACT_LENGTH,
    USER_CITY_LENGTH,
    USER_COUNTRY_LENGTH,
    USER_EMAIL_HELP,
    USER_EMAIL_LENGTH,
    USER_GROUP_NAME,
    USER_NAME_HELP,
    USER_NAME_LENGTH,
    USER_NAME_MIN_LENGTH,
    USER_NAME_PATTERN,
    USER_ROLE_LENGTH,
    USER_SURNAME_HELP,
    USER_SURNAME_LENGTH,
    USER_SURNAME_MIN_LENGTH,
)
from core.models.mixins import BusinessDateTimeMixin
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    Group,
    PermissionsMixin,
)
from django.core.validators import (
    MinLengthValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .providers import OauthProvider


class UserManager(BaseUserManager):
    """Менеджер пользователя с email в качестве логина."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Создает и сохраняет пользователя с введенным им email и паролем."""
        if not email:
            raise ValueError('Email обязателен.')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', User.RoleChoices.USER)
        user = self._create_user(email, password, **extra_fields)
        self._add_to_group(user, USER_GROUP_NAME)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_confirmed', True)
        extra_fields.setdefault('is_password_confirmed', True)
        extra_fields.setdefault('is_agreed_to_terms', True)
        extra_fields.setdefault('role', User.RoleChoices.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('У суперпользователя is_staff должен быть True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(
                'У суперпользователя is_superuser должен быть True.'
            )

        user = self._create_user(email, password, **extra_fields)
        self._add_to_group(user, ADMIN_GROUP_NAME)
        return user

    def _add_to_group(self, user, group_name):
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)


class User(BusinessDateTimeMixin, AbstractBaseUser, PermissionsMixin):
    """Кастомная модель пользователя с email в качестве логина."""

    class RoleChoices(models.TextChoices):
        USER = 'user', 'Пользователь'
        MODERATOR = 'moderator', 'Модератор'
        ADMIN = 'admin', 'Администратор'

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'surname']

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
    provider = models.ForeignKey(
        OauthProvider,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='OAuth-провайдер',
        help_text='OAuth-провайдер пользователя.',
    )
    email = models.EmailField(
        'Электронная почта',
        max_length=USER_EMAIL_LENGTH,
        help_text=USER_EMAIL_HELP,
        unique=True,
    )
    is_staff = models.BooleanField(
        'Доступ в админку',
        default=False,
        help_text='Отмечает, может ли пользователь входить в админку.',
    )
    is_active = models.BooleanField(
        'Активен',
        default=True,
        help_text='Отмечает активного пользователя.',
    )
    date_joined = models.DateTimeField(
        'Дата регистрации',
        default=timezone.now,
        help_text='Дата и время регистрации пользователя.',
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
    password = models.CharField(
        'Хэш пароля',
        max_length=128,
        db_column='password_hash',
        help_text='Хэш пароля пользователя.',
    )
    is_password_confirmed = models.BooleanField(
        'Пароль подтверждён',
        default=False,
        help_text='Отмечает, подтверждён ли пароль пользователя.',
    )
    name = models.CharField(
        'Имя',
        help_text=USER_NAME_HELP,
        max_length=USER_NAME_LENGTH,
        validators=[
            MinLengthValidator(
                USER_NAME_MIN_LENGTH,
                message=(
                    'Имя не может быть короче '
                    f'{USER_NAME_MIN_LENGTH} символов(а)'
                ),
            ),
            RegexValidator(
                regex=USER_NAME_PATTERN,
                message='Допускаются только буквы кириллицы или латиницы.',
            ),
        ],
    )
    surname = models.CharField(
        'Фамилия',
        help_text=USER_SURNAME_HELP,
        max_length=USER_SURNAME_LENGTH,
        validators=[
            MinLengthValidator(
                USER_SURNAME_MIN_LENGTH,
                message=(
                    'Фамилия не может быть короче '
                    f'{USER_SURNAME_MIN_LENGTH} символов(а)'
                ),
            ),
            RegexValidator(
                regex=USER_NAME_PATTERN,
                message='Допускаются только буквы кириллицы или латиницы.',
            ),
        ],
    )
    is_agreed_to_terms = models.BooleanField(
        'Согласие с условиями',
        default=False,
        help_text='Пользователь согласился с условиями использования.',
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
            )
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
        ordering = ('-create_date_time',)
        constraints = (
            models.UniqueConstraint(
                fields=('new_email',),
                condition=~Q(new_email=''),
                name='unique_not_empty_new_email',
            ),
        )

    def get_full_name(self):
        """Возвращает name и surname с пробелом между ними."""
        full_name = '%s %s' % (self.name, self.surname)
        return full_name.strip()

    def get_short_name(self):
        """Возвращает сокращенное имя пользователя."""
        return self.name

    def __str__(self) -> str:
        return self.email
