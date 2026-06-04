from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Конфиг базового приложения."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Базовое приложение'
