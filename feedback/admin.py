from django.contrib import admin

from .models import FeedbackForm, FeedbackImage


@admin.register(FeedbackForm)
class FeedbackFormAdmin(admin.ModelAdmin):
    """Админ‑панель для модели FeedbackForm."""

    list_display = '__all__'


@admin.register(FeedbackImage)
class FeedbackImageAdmin(admin.ModelAdmin):
    """Админ‑панель для модели FeedbackImage."""

    list_display = '__all__'
