from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Приложение авторизации."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
