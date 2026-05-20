from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """Конфиг приложения проектов."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'
    verbose_name = 'Проекты'
