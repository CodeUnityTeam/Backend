from typing import Any

from rest_framework import permissions
from rest_framework.request import Request

from feedback.models import Review


class CanEditDeleteReview(permissions.BasePermission):
    """Разрешает изменение/удаление отзыва.

    Доступно только автору, модератору или админу.
    """

    def has_object_permission(
        self,
        request: Request,
        view: Any,
        obj: Review,
    ) -> bool:
        """Проверяет, может ли пользователь изменить или удалить отзыв."""
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        user = request.user
        return (
            obj.user == user
            or user.role == 'moderator'
            or user.role == 'admin'
            or user.is_superuser
        )
