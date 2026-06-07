from django.apps import AppConfig


class QnaConfig(AppConfig):
    """Конфиг приложения вопросов и ответов."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'qna'
    verbose_name = 'Вопросы и ответы'

    def ready(self) -> None:  # noqa: D102
        import qna.signals  # noqa: F401, W291
