from django.contrib import admin
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from core.admin_mixins import RolePermissionsMixin
from qna.forms import ImageAdminForm

from .models import FeedbackForm, FeedbackImage
from .services import feedback_image_upload_handler


class FeedbackImageInline(admin.TabularInline):
    """Изображения, прикреплённые к форме обратной связи."""

    model = FeedbackImage
    form = ImageAdminForm
    extra = 0
    fields = ('post_image', 'image_url')
    readonly_fields = ('post_image', 'image_url')
    can_delete = False


@admin.register(FeedbackForm)
class FeedbackFormAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ‑панель для модели FeedbackForm."""

    list_display = (
        'feedback_id',
        'subject',
        'status',
        'user',
        'created_at',
        'updated_at',
    )
    inlines = (FeedbackImageInline,)


@admin.register(FeedbackImage)
class FeedbackImageAdmin(RolePermissionsMixin, admin.ModelAdmin):
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
            public_url: str = feedback_image_upload_handler(file_obj=file_obj)
            obj.image_url = public_url
            obj.original_name = file_obj.name
            obj.file_size = file_obj.size
            obj.mime_type = file_obj.content_type or 'image/jpeg'

        super().save_model(request, obj, form, change)
