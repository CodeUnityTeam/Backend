from django.apps import AppConfig


class AuthConfig(AppConfig):
    """Конфиг приложения аутентификации."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
