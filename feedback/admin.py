from django.contrib import admin
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from qna.forms import ImageAdminForm
from qna.services import image_upload_handler

from .models import FeedbackForm, FeedbackImage


@admin.register(FeedbackForm)
class FeedbackFormAdmin(admin.ModelAdmin):
    """Админ‑панель для модели FeedbackForm."""

    list_display = (
        'feedback_id',
        'subject',
        'status',
        'user',
        'created_at',
        'updated_at',
    )


@admin.register(FeedbackImage)
class FeedbackImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели FeedbackImage."""

    form = ImageAdminForm
    exclude = ('image_url', 'original_name', 'file_size', 'mime_type')

    list_display = (
        'feedback_image',
        'feedback',
        'original_name',
        'file_size',
        'mime_type',
        'created_at',
        'image_url',
        'post_image',
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: FeedbackImage,
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
