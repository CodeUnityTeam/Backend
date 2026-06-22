from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """Конфиг приложения проектов."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'
    verbose_name = 'Проекты'

    def ready(self) -> None:
        """Подключаем сигналы при готовности приложения."""
        import projects.signals  # noqa: F401
