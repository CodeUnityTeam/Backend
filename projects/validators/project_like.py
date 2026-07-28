from django.contrib.auth import get_user_model
from rest_framework import exceptions

from core.constants.projects import ALLOWED_STATUSED_FOR_LIKE
from projects.models import Project

User = get_user_model()


def validate_project_like(
    project: Project,
    user: User,
) -> None:
    """Проверяет возможность поставить лайк проекту.

    Ограничения:
    - Нельзя лайкнуть свой проект.
    - Можно лайкать только PUBLISHED или RECRUITING_CLOSED.
    """
    if project.author == user:
        raise exceptions.PermissionDenied('Нельзя лайкнуть свой проект.')
    if project.status_project not in ALLOWED_STATUSED_FOR_LIKE:
        raise exceptions.PermissionDenied(
            'Нельзя лайкать проект с текущим статусом.',
        )
