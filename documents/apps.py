from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """Приложение для работы с PDF-документами."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documents'
