from django.contrib import admin
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from qna.forms import ImageAdminForm
from qna.services import image_upload_handler

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

    form = ImageAdminForm
    list_display = (
        'question',
        'image_id',
        'image_url',
        'post_image',
    )
    exclude = ('image_url', 'original_name', 'file_size', 'mime_type')

    def save_model(
        self,
        request: HttpRequest,
        obj: QuestionImage,
        form: any,
        change: bool,
    ) -> None:
        """Загружает файл в MinIO и сохраняет URL в модель."""
        file_obj: UploadedFile | None = request.FILES.get('file')

        if file_obj:
            public_url: str = image_upload_handler(file_obj=file_obj)
            obj.image_url = public_url
            obj.original_name = file_obj.name
            obj.file_size = file_obj.size
            obj.mime_type = file_obj.content_type or 'image/jpeg'

        super().save_model(request, obj, form, change)


@admin.register(AnswerImage)
class AnswerImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели AnswerImage."""

    form = ImageAdminForm
    list_display = (
        'answer',
        'image_id',
        'image_url',
        'post_image',
    )
    exclude = ('image_url', 'original_name', 'file_size', 'mime_type')

    def save_model(
        self,
        request: HttpRequest,
        obj: AnswerImage,
        form: any,
        change: bool,
    ) -> None:
        """Загружает файл в MinIO и сохраняет URL в модель."""
        file_obj: UploadedFile | None = request.FILES.get('file')

        if file_obj:
            public_url: str = image_upload_handler(file_obj=file_obj)
            obj.image_url = public_url
            obj.original_name = file_obj.name
            obj.file_size = file_obj.size
            obj.mime_type = file_obj.content_type or 'image/jpeg'

        super().save_model(request, obj, form, change)


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
