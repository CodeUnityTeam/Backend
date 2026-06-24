from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from core.constants.projects import PUBLISHED, RECRUITING_CLOSED
from projects.models import Project

User = get_user_model()


def validate_project_favorite(project: Project, user: User) -> None:
    """Проверка бизнес‑правил для добавления в избранное."""
    if project.author == user:
        raise ValidationError('Нельзя добавить в избранное свой проект.')
    if project.status_project not in (PUBLISHED, RECRUITING_CLOSED):
        raise ValidationError(
            'В избранное можно добавить только проекты со статусом '
            '{PUBLISHED} или {RECRUITING_CLOSED}.',
        )
