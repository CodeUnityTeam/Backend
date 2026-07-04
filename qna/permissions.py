from typing import Any

from rest_framework import permissions
from rest_framework.request import Request

from qna.models import Answer, Question


class CanUpdateDeleteQNA(permissions.BasePermission):
    """Разрешает удаление/обновление автору, модератору или админу."""

    def has_object_permission(
        self,
        request: Request,
        view: Any,
        obj: Answer | Question,
    ) -> bool:
        """Проверяет, может ли пользователь удалить ответ."""
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return (
            obj.user == user
            or user.role == 'moderator'
            or user.role == 'admin'
            or user.is_superuser
        )
