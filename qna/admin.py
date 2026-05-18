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

    list_display = '__all__'


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Админ‑панель для модели Answer."""

    list_display = '__all__'


@admin.register(QuestionImage)
class QuestionImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели QuestionImage."""

    list_display = '__all__'


@admin.register(AnswerImage)
class AnswerImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели AnswerImage."""

    list_display = '__all__'


@admin.register(QuestionLike)
class QuestionLikeAdmin(admin.ModelAdmin):
    """Админ‑панель для модели QuestionLike."""

    list_display = '__all__'


@admin.register(AnswerLike)
class AnswerLikeAdmin(admin.ModelAdmin):
    """Админ‑панель для модели AnswerLike."""

    list_display = '__all__'
