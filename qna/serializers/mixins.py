from typing import Any


class AuthorInfoMixin:
    """Миксин для сериализаторов QnA с полями author_name и author_rating."""

    def get_author_name(self, obj: Any) -> str:
        """Возвращает имя автора или 'Аноним' (для вопросов)."""
        if getattr(obj, 'is_anonymous', False):
            return 'Аноним'
        user = obj.user
        return (
            f'{user.first_name} {user.last_name}'.strip()
            or user.email
        )

    def get_author_rating(self, obj: Any) -> int:
        """Возвращает рейтинг автора (0 для анонимных вопросов)."""
        if getattr(obj, 'is_anonymous', False):
            return 0
        return obj.user.rating
