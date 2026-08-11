
from django.contrib import admin

from core.admin_mixins import (
    BaseImageInline,
    BaseLikeInline,
    LikeCountMixin,
    SaveImageFormsetMixin,
)
from minio.s3_utils import MediaType

from .models import (
    Answer,
    AnswerImage,
    AnswerLike,
    Question,
    QuestionImage,
    QuestionLike,
)


class QuestionLikeInline(BaseLikeInline):
    """Инлайн для управления лайками вопроса."""

    model = QuestionLike
    verbose_name = 'Лайк вопроса'
    verbose_name_plural = 'Лайки вопроса'


class AnswerLikeInline(BaseLikeInline):
    """Инлайн для управления лайками ответа."""

    model = AnswerLike
    verbose_name = 'Лайк ответа'
    verbose_name_plural = 'Лайки ответа'


class QuestionImageInline(BaseImageInline):
    """Изображения, прикреплённые к вопросу."""

    model = QuestionImage
    media_type = MediaType.QUESTION_IMAGE


class AnswerImageInline(BaseImageInline):
    """Изображения, прикреплённые к ответу."""

    model = AnswerImage
    media_type = MediaType.ANSWER_IMAGE


@admin.register(Question)
class QuestionAdmin(SaveImageFormsetMixin, LikeCountMixin, admin.ModelAdmin):
    """Админ‑панель для модели Question."""

    list_display = (
        'question_id',
        'user',
        'title',
        'like_count',
        'created_at',
    )
    inlines = (QuestionImageInline, QuestionLikeInline)


@admin.register(Answer)
class AnswerAdmin(SaveImageFormsetMixin, LikeCountMixin, admin.ModelAdmin):
    """Админ‑панель для модели Answer."""

    list_display = (
        'answer_id',
        'question',
        'user',
        'like_count',
        'created_at',
    )
    inlines = (AnswerImageInline, AnswerLikeInline)
