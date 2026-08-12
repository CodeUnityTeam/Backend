import uuid

from django.core.validators import MinLengthValidator
from django.db import models

from core.constants.qna import (
    MAX_CONTENT_ANSWER,
    MAX_TITLE_QUESTION,
    MIN_DESC_QUESTION,
    MIN_TITLE_QUESTION,
)
from core.models.mixins import BaseImageMixin, TimestampMixin
from users.models import Skill


class Question(TimestampMixin, models.Model):
    """Вопрос, созданный пользователем в разделе Q&A.

    - Может быть анонимным.
    - Поддерживает редактирование (обновляется updated_at).
    - Деактивируется модератором.
    """

    question_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор вопроса',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='questions',
        verbose_name='Автор вопроса',
    )
    title = models.CharField(
        max_length=MAX_TITLE_QUESTION,
        validators=[MinLengthValidator(MIN_TITLE_QUESTION)],
        verbose_name='Заголовок вопроса',
    )
    description = models.TextField(
        validators=[MinLengthValidator(MIN_DESC_QUESTION)],
        verbose_name='Полное описание вопроса',
    )
    is_anonymous = models.BooleanField(
        default=False,
        verbose_name='Опубликовано анонимно',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
    )
    skills = models.ManyToManyField(
        Skill,
        related_name='questions',
        db_table='question_tags',
        verbose_name='Навыки для вопроса',
    )

    class Meta:
        """Метаданные модели."""

        ordering = ('-created_at',)
        db_table = 'questions'
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        indexes = (
            models.Index(fields=['-created_at']),  # поля из миксина
            models.Index(fields=['-updated_at']),  # поля из миксина
            models.Index(fields=['is_active']),
            models.Index(fields=['is_anonymous']),
        )

    def __str__(self) -> str:
        return self.title


class Answer(models.Model):
    """Ответ пользователя на вопрос в разделе Q&A."""

    answer_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Идентификатор ответа',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='answers',
        verbose_name='Вопрос',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='answers',
        verbose_name='Автор ответа',
    )
    parent_answer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        db_column='parent_answer_id',
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='Родительский ответ',
    )
    content = models.TextField(
        max_length=MAX_CONTENT_ANSWER,
        verbose_name='Текст ответа',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'answers'
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        indexes = (
            models.Index(fields=['question', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['parent_answer']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_active']),
        )

    def __str__(self) -> str:
        short_content = self.content[:75]
        return f'Ответ на "{self.question.title}": {short_content}...'


class QuestionLike(models.Model):
    """Лайки, поставленные пользователями вопросам."""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='question_likes',
        verbose_name='Пользователь',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='likes',
        verbose_name='Вопрос',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата лайка',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'question_likes'
        verbose_name = 'Лайк вопроса'
        verbose_name_plural = 'Лайки вопросов'
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'question'],
                name='unique_user_question_like',
            ),
        )
        indexes = (
            models.Index(fields=['created_at']),
        )

    def __str__(self) -> str:
        return (
            f'{self.user.first_name} поставил '
            'лайк вопросу "{self.question.title}"'
        )


class AnswerLike(models.Model):
    """Лайки, поставленные пользователями ответам."""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='answer_likes',
        verbose_name='Пользователь',
    )
    answer = models.ForeignKey(
        'Answer',
        on_delete=models.CASCADE,
        db_column='answer_id',
        related_name='likes',
        verbose_name='Ответ',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата лайка',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'answer_likes'
        verbose_name = 'Лайк ответа'
        verbose_name_plural = 'Лайки ответов'
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'answer'],
                name='unique_user_answer_like',
            ),
        )
        indexes = (
            models.Index(fields=['created_at']),
        )

    def __str__(self) -> str:
        return f'{self.user.first_name} ответ на {self.answer.question.title}'


class QuestionImage(BaseImageMixin):
    """Изображения, прикреплённые к вопросу.

    - Хранит метаданные и URL изображения.
    - Привязано к вопросу и пользователю, который загрузил.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='images',
        verbose_name='Вопрос',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'question_image'
        verbose_name = 'Изображение вопроса'
        verbose_name_plural = 'Изображения вопроса'
        indexes = (
            models.Index(fields=['question']),
        )

    def __str__(self) -> str:
        return f'Изображение {self.original_name} для "{self.question.title}"'


class AnswerImage(BaseImageMixin):
    """Изображения, прикреплённые к ответу на вопрос.

    - Хранит метаданные и URL изображения.
    - Привязано к ответу и пользователю, который загрузил.
    """

    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        db_column='answer_id',
        related_name='images',
        verbose_name='Ответ',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'answer_image'
        verbose_name = 'Изображение ответа'
        verbose_name_plural = 'Изображения ответов'
        indexes = (
            models.Index(fields=['answer']),
        )

    def __str__(self) -> str:
        return (
            f'Изображение {self.original_name} для '
            f'"{self.answer.question.title}"'
        )
