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
        'create_date_time',
        'update_date_time',
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
        'uploaded_at',
        'image_url',
    )
