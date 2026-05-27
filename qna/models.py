import uuid

from django.db import models

from core.constants.qna import (
    MAX_CONTENT_ANSWER,
    MAX_LEN_TITLE,
    ZERO_LIKE_COUNT,
)
from core.models.mixins import BaseImageMixin, CreatedAtMixin, TimestampMixin
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
        max_length=MAX_LEN_TITLE,
        verbose_name='Заголовок вопроса',
    )
    description = models.TextField(
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

        db_table = 'questions'
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['-updated_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_anonymous']),
        ]

    def __str__(self) -> str:
        return self.title


class Answer(CreatedAtMixin, models.Model):
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
    likes_count = models.IntegerField(
        default=ZERO_LIKE_COUNT,
        verbose_name='Количество лайков',
    )

    class Meta:
        """Метаданные модели."""

        db_table = 'answers'
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        indexes = [
            models.Index(fields=['question', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['parent_answer']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['likes_count']),
        ]

    def __str__(self) -> str:
        short_content = self.content[:75]
        return f'Ответ на "{self.question.title}": {short_content}...'


class QuestionLike(CreatedAtMixin, models.Model):
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

    class Meta:
        """Метаданные модели."""

        db_table = 'question_likes'
        unique_together = ('user', 'question')
        verbose_name = 'Лайк вопроса'
        verbose_name_plural = 'Лайки вопросов'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'question'],
                name='unique_user_question_like',
            ),
        ]
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return (
            f'{self.user.first_name} поставил '
            'лайк вопросу "{self.question.title}"'
        )


class AnswerLike(CreatedAtMixin, models.Model):
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

    class Meta:
        """Метаданные модели."""

        db_table = 'answer_likes'
        unique_together = ('user', 'answer')
        verbose_name = 'Лайк ответа'
        verbose_name_plural = 'Лайки ответов'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'answer'],
                name='unique_user_answer_like',
            ),
        ]
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.user.first_name} ответ на {self.answer.question.title}'


class QuestionImage(BaseImageMixin, models.Model):
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
        indexes = [
            models.Index(fields=['question']),
            models.Index(fields=['uploaded_by']),
        ]

    def __str__(self) -> str:
        return f'Изображение {self.image_id} для "{self.question.title}"'


class AnswerImage(BaseImageMixin, models.Model):
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
        indexes = [
            models.Index(fields=['answer']),
            models.Index(fields=['uploaded_by']),
        ]

    def __str__(self) -> str:
        return (
            f'Изображение {self.image_id} для '
            f'"{self.answer.question.title}"'
        )
