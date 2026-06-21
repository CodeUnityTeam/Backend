from django.contrib.auth import get_user_model
from django.db import transaction

from core.constants.projects import (
    ALLOWED_STATUSED_FOR_LIKE,
    APPLICANT,
    MEMBER,
    PENDING,
)

from .models import Project, ProjectLike, ProjectParticipant, Response

User = get_user_model()


def create_response(
    project: Project,
    user: User,
    initiator_type: str = APPLICANT,
    status_resp: str = PENDING,
) -> Response:
    """Создаёт новый отклик на проект."""
    return Response.objects.create(
        project=project,
        user=user,
        initiator_type=initiator_type,
        status_resp=status_resp,
    )


def add_user_to_project_participants(
    project: Project,
    user: User,
    status: str = MEMBER,
) -> ProjectParticipant:
    """Добавляет пользователя в участники проекта."""
    participant, _ = ProjectParticipant.objects.get_or_create(
        project=project,
        user=user,
        status_participant=status,
    )
    return participant


def toggle_project_like(project: Project, user: User) -> dict:
    """Переключает лайк проекта: создаёт или удаляет.

    Ограничения:
    - Нельзя лайкнуть свой проект.
    - Можно лайкать только PUBLISHED или RECRUITING_CLOSED.
    """
    if project.author == user:
        raise ValueError('Нельзя лайкнуть свой проект.')

    if project.status_project not in ALLOWED_STATUSED_FOR_LIKE:
        raise ValueError(
            'Нельзя лайкать проект с текущим статусом.',
        )
    with transaction.atomic():
        like, created = ProjectLike.objects.select_for_update().get_or_create(
            project=project,
            user=user,
        )
        if not created:
            like.delete()
        likes_count = ProjectLike.objects.filter(project=project).count()
    return {'liked': created, 'likes_count': likes_count}
