from typing import Any

from django.apps import apps
from rest_framework import permissions
from rest_framework.request import Request

from .models import Project

User = apps.get_model('users', 'User')


class IsEmployer(permissions.BasePermission):
    """Единый permission для действий над проектами.

    - create: только аутентифицированный наниматель.
    - update/partial_update: автор-наниматель, суперюзер, админ.
    - destroy (архивация): автор-наниматель, суперюзер, админ.
    """

    def has_permission(self, request: Request, view: Any) -> bool:
        """Проверяет возможность выполнения действия."""
        if view.action == 'create':
            return (
                request.user.is_authenticated
                and request.user.projects_relation
                == User.ProjectsRelationChoices.EMPLOYER
            )
        if view.action in ('update', 'partial_update', 'destroy'):
            return request.user.is_authenticated
        return True

    def has_object_permission(
        self,
        request: Request,
        view: Any,
        obj: Project,
    ) -> bool:
        """Проверяет права на объект.

        Для update/partial_update/destroy:
        - суперюзер или админ — всегда разрешено.
        - автор-наниматель — разрешено.
        """
        if view.action not in ('update', 'partial_update', 'destroy'):
            return True
        user = request.user
        if user.is_superuser or user.role == 'admin':
            return True
        return (
            obj.author == user
            and user.projects_relation
            == User.ProjectsRelationChoices.EMPLOYER
        )


class IsWorker(permissions.BasePermission):
    """Permission для действий над откликами."""

    def has_permission(self, request: Request, view: Any) -> bool:
        """Проверяет возможность выполнения действия."""
        return (
            request.user.is_authenticated
            and request.user.projects_relation
            == User.ProjectsRelationChoices.WORKER
        )
