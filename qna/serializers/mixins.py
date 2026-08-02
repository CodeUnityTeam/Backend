from typing import Any

from qna.models import Question


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


class IsLikedByMeMixin:
    """Миксин для получения поля - лайкнул ли текущий юзер вопрос."""

    def get_is_liked_by_me(self, obj: Question) -> bool:
        """Проверяем лайк юзера на вопрос.

        Для анонимов всегда False.
        """
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return False
        user = request.user
        if user.is_anonymous:
            return False
        likes_qs = getattr(obj, 'likes', None)
        if not likes_qs:
            return False
        return any(like.user_id == user.pk for like in likes_qs.all())
