from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    """Конфиг приложения обратной связи."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feedback'
    verbose_name = 'Обратная связь'
