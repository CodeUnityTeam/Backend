import uuid
from typing import Any

from django.contrib.auth.models import (
    AbstractUser,
)
from django.core.exceptions import ValidationError
from django.core.validators import (
    RegexValidator,
)
from django.db import models
from django.db.models import Q

from config import settings
from core.constants.users import (
    MAX_CHAR_FIELD_LENGTH,
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
from core.models.mixins import CreatedAtMixin, TimestampMixin

from .managers import UserManager


class User(TimestampMixin, AbstractUser):
    """Кастомная модель пользователя на базе стандартного AbstractUser."""

    class RoleChoices(models.TextChoices):
        USER = 'user', 'Пользователь'
        MODERATOR = 'moderator', 'Модератор'
        ADMIN = 'admin', 'Администратор'

    class ProjectsRelationChoices(models.TextChoices):
        EMPLOYER = 'employer', 'Наниматель'
        WORKER = 'worker', 'Работник'

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ('first_name', 'last_name')
    objects = UserManager()

    username = models.CharField(
        max_length=MAX_CHAR_FIELD_LENGTH,
        unique=True,
        blank=True,
        null=True,
    )
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
    projects_relation = models.CharField(
        'Роль в проектах',
        choices=ProjectsRelationChoices.choices,
        default=ProjectsRelationChoices.WORKER,
        help_text='Роль по отношению к проектам (наниматель или исполнитель).',
    )
    email = models.EmailField(
        'Электронная почта',
        max_length=USER_EMAIL_LENGTH,
        help_text=USER_EMAIL_HELP,
        unique=True,
    )
    new_email = models.EmailField(
        'Новая электронная почта',
        max_length=USER_EMAIL_LENGTH,
        help_text=USER_EMAIL_HELP,
        blank=True,
        default='',
    )
    is_email_confirmed = models.BooleanField(
        'Email подтверждён',
        default=False,
        help_text='Отмечает, подтверждён ли email пользователя.',
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
        validators=(
            RegexValidator(
                regex=USER_NAME_PATTERN,
                message=USER_NAME_HELP,
            ),
        ),
    )
    last_name = models.CharField(
        'Фамилия',
        max_length=USER_LAST_NAME_LENGTH,
        validators=(
            RegexValidator(
                regex=USER_NAME_PATTERN,
                message=USER_NAME_HELP,
            ),
        ),
    )
    phone_number = models.CharField(
        'Номер телефона',
        max_length=MAX_PHONE_DIGITS,
        blank=True,
        default='',
        validators=(
            RegexValidator(
                regex=PHONE_PATTERN,
                message=(
                    'Телефон должен начинаться с + и содержать от '
                    f'{MIN_PHONE_DIGITS} до {MAX_PHONE_DIGITS} цифр.'
                ),
            ),
        ),
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
    soft_skills = models.TextField(
        'Личные качества',
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
    workformats = models.ManyToManyField(
        'projects.WorkFormat',
        through='UserWorkFormat',
        related_name='users',
        verbose_name='Формат работы',
        blank=True,
    )
    rating = models.PositiveIntegerField(
        'Рейтинг пользователя',
        default=0,
        help_text='Сумма лайков ко всем вопросам и ответам пользователя',
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


class UserExperience(TimestampMixin):
    """Моедль опыта работы пользователя."""

    exp_id = models.UUIDField(
        'ID записи опыта пользователя',
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Уникальный идентификатор.',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='experiences',
        verbose_name='Пользователь',
        help_text='Пользователь, опыт которого описывается.',
    )
    company = models.CharField(
        max_length=MAX_CHAR_FIELD_LENGTH,
        verbose_name='Компания',
        help_text='Название организации.',
    )
    position = models.CharField(
        max_length=MAX_CHAR_FIELD_LENGTH,
        verbose_name='Должность',
        help_text='Занимаемая должность.',
    )
    responsibilities = models.TextField(
        verbose_name='Обязанности',
        help_text='Описание задач и достижений.',
        blank=True,
    )
    start_date = models.DateField(
        verbose_name='Дата начала работы',
    )
    end_date = models.DateField(
        verbose_name='Дата окончания работы',
        blank=True,
        null=True,
        help_text='Оставьте пустым, если работаете здесь по настоящее время.',
    )

    class Meta:
        verbose_name = 'Опыт работы'
        verbose_name_plural = 'Опыт работы'
        ordering = ('-start_date',)
        indexes = (
            models.Index(fields=('user', '-start_date')),
        )

    def __str__(self) -> str:
        return f'{self.user} — {self.position} в {self.company}'


class UserLike(CreatedAtMixin, models.Model):
    """Лайки, поставленные автором проекта другим пользователям."""

    employer = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        db_column='employer_id',
        related_name='liked_workers',
        verbose_name='Автор лайка',
    )
    worker = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        db_column='worker_id',
        related_name='employers_likes',
        verbose_name='Лайкнутый пользователь',
    )

    class Meta:
        db_table = 'user_likes'
        verbose_name = 'Лайк пользователя'
        verbose_name_plural = 'Лайки пользователя'
        constraints = (
            models.UniqueConstraint(
                fields=('employer', 'worker'),
                name='unique_like_employer_worker',
            ),
        )
        indexes = (
            models.Index(fields=('created_at',)),
        )

    def clean(self) -> None:
        """Проверка бизнес-логики перед сохранением."""
        super().clean()

        if self.employer_id == self.worker_id:
            raise ValidationError('Нельзя лайкнуть свой профиль.')

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Принудительный запуск валидации перед записью в БД."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f'Лайк пользователя {self.employer} '
            f'на пользователя {self.worker}'
        )
