from django.contrib import admin

from .models import (
    Answer,
    AnswerImage,
    AnswerLike,
    Question,
    QuestionImage,
    QuestionLike,
)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Админ‑панель для модели Question."""

    list_display = (
        'question_id',
        'user',
        'title',
        'created_at',
    )


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Админ‑панель для модели Answer."""

    list_display = (
        'answer_id',
        'question',
        'user',
        'created_at',
    )


@admin.register(QuestionImage)
class QuestionImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели QuestionImage."""

    list_display = (
        'question',
        'image_id',
    )


@admin.register(AnswerImage)
class AnswerImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели AnswerImage."""

    list_display = (
        'answer',
        'image_id',
    )


@admin.register(QuestionLike)
class QuestionLikeAdmin(admin.ModelAdmin):
    """Админ‑панель для модели QuestionLike."""

    list_display = (
        'question',
        'user',
    )


@admin.register(AnswerLike)
class AnswerLikeAdmin(admin.ModelAdmin):
    """Админ‑панель для модели AnswerLike."""

    list_display = (
        'answer',
        'user',
    )
