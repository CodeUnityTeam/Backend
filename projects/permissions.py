from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.request import Request

from .models import Project

User = get_user_model()


def can_archive_project(user: User, project: Project) -> bool:
    """Проверяет, может ли пользователь архивировать проект."""
    return (
        user.is_superuser or
        user.is_staff or
        project.author == user or
        user.role == 'admin'
    )


# TODO [PROJECTS]: has_permission в CanArchiveProject всегда возвращает True.
#   Метод has_permission (строка 25) возвращает True для любого запроса,
#   независимо от метода и пользователя. Фактическая проверка прав происходит
#   только в has_object_permission (строка 31), но она вызывается только если
#   has_permission вернул True. Это ок, но has_permission должен хотя бы
#   проверять аутентификацию: return request.user.is_authenticated.
#   Иначе неаутентифицированные пользователи могут пытаться архивировать.
class CanArchiveProject(permissions.BasePermission):
    """Разрешает архивировать проект: суперюзеру, админу или автору."""

    def has_permission(self, request: Request, view: Any) -> bool:
        """Проверяет возможность выполнения действия."""
        if request.method == 'DELETE':
            return True
        return True

    def has_object_permission(
        self,
        request: Request,
        view: Any,
        obj: Project,
    ) -> bool:
        """Проверяет права доступа к объекту для DELETE‑запросов."""
        if request.method != 'DELETE':
            return False
        return can_archive_project(request.user, obj)
