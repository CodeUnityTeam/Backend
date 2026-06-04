from django.contrib import admin

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

    list_display = (
        'feedback_image',
        'feedback',
        'original_name',
        'file_size',
        'mime_type',
        'created_at',
        'image_url',
    )
