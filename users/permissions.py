from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from users.models.users import User


class IsEmployer(BasePermission):
    """Разрешает доступ только пользователям с ролью EMPLOYER."""

    def has_permission(
        self, request: Request, view: APIView
    ) -> bool:
        """Проверяет роль текущего пользователя."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.projects_relation
            == User.ProjectsRelationChoices.EMPLOYER
        )
