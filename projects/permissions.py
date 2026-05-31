from typing import Any

from rest_framework import permissions
from rest_framework.request import Request

from .models import Project
from .selectors import can_archive_project


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
