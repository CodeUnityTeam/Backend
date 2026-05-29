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
        'create_at',
        'update_at',
    )


@admin.register(FeedbackImage)
class FeedbackImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели FeedbackImage."""

    list_display = (
        'image_id',
        'feedback',
        'original_name',
        'file_size',
        'mime_type',
        'uploaded_at',
        'image_url',
    )
