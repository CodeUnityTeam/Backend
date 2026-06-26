from django.apps import AppConfig


class HelpConfig(AppConfig):
    """Вспомогательное приложение."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'help'

    def ready(self) -> None:
        """Подключаем сигналы при готовности приложения."""
        import help.signals  # noqa: F401
