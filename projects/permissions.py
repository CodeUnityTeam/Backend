from typing import Any

from django.apps import apps
from rest_framework import permissions
from rest_framework.request import Request

from .models import Project

User = apps.get_model('users', 'User')


def can_archive_project(user: User, project: Project) -> bool:
    """Проверяет, может ли пользователь архивировать проект.

    Разрешено:
    - суперюзеру
    - администратору (user.role == 'admin')
    - автору проекта, если он наниматель (EMPLOYER)
    """
    if user.is_superuser or user.role == 'admin':
        return True
    return (
        project.author == user
        and user.projects_relation == User.ProjectsRelationChoices.EMPLOYER
    )


class CanArchiveProject(permissions.BasePermission):
    """Разрешает архивировать проект: суперюзеру/админу/автору-нанимателю."""

    def has_permission(self, request: Request, view: Any) -> bool:
        """Проверяет возможность выполнения действия.

        Для DELETE — только авторизованные пользователи.
        Дальнейшая проверка прав на объект — в has_object_permission.
        """
        if request.method == 'DELETE':
            return request.user.is_authenticated
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


class IsEmployer(permissions.BasePermission):
    """Только наниматели могут создавать проекты."""

    def has_permission(self, request: Request, view: Any) -> bool:
        """Проверяем что юзер авторизован и является нанимателем."""
        if view.action == 'create':
            return (
                request.user.is_authenticated
                and request.user.projects_relation
                == User.ProjectsRelationChoices.EMPLOYER
            )
        return True
