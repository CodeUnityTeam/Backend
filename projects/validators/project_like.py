from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404

from core.constants.projects import ALLOWED_STATUSED_FOR_LIKE, ARCHIVED
from projects.models import Project

User = get_user_model()


def validate_project_like(
    project: Project,
    user: User,
) -> None:
    """Проверяет возможность поставить лайк проекту.

    Ограничения:
    - Нельзя лайкнуть свой проект (400).
    - Можно лайкать только PUBLISHED или RECRUITING_CLOSED.
    - Архивный проект недоступен для лайка — возвращается 404,
      так как такой проект не должен быть доступен через API.
    - Иные статусы (draft, blocked) — 400.
    """
    if project.author == user:
        raise ValidationError('Нельзя лайкнуть свой проект.')
    if project.status_project not in ALLOWED_STATUSED_FOR_LIKE:
        if project.status_project == ARCHIVED:
            raise Http404(
                'Проект недоступен для лайка.',
            )
        raise ValidationError(
            'Нельзя лайкать проект с текущим статусом.',
        )
