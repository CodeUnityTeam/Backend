from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Приложение пользователей."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self) -> None:
        """Подключаем сигналы при готовности приложения."""
        import users.signals  # noqa: F401
