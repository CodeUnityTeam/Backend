from django.apps import AppConfig


class AuthConfig(AppConfig):
    """Приложение авторизации."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
