from django.contrib import admin

from core.admin_mixins import (
    BaseImageInline,
    RolePermissionsMixin,
)
from minio.s3_utils import MediaType

from .models import FeedbackForm, FeedbackImage, Review


@admin.register(Review)
class ReviewAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ‑панель для модели Review."""

    list_display = (
        'review_id',
        'user',
        'text',
        'created_at',
    )
    list_select_related = ('user',)
    search_fields = ('text', 'user__email', 'user__first_name')
    ordering = ('-created_at',)


class FeedbackImageInline(BaseImageInline):
    """Изображения, прикреплённые к форме обратной связи."""

    model = FeedbackImage
    media_type = MediaType.FEEDBACK_IMAGE


@admin.register(FeedbackForm)
class FeedbackFormAdmin(
    RolePermissionsMixin,
    admin.ModelAdmin,
):
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
