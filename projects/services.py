from django.contrib.auth import get_user_model
from django.db import transaction

from core.constants.projects import APPLICANT, MEMBER, PENDING
from projects.models import (
    Project,
    ProjectFavorite,
    ProjectLike,
    ProjectParticipant,
    Response,
)
from projects.validators import validate_project_like
from projects.validators.project_favorite import validate_project_favorite
from projects.validators.project_like import validate_project_like

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
    """Переключает состояние лайка для проекта указанным пользователем.

    Если лайк уже существует, он удаляется; если отсутствует — создаётся.
    """
    validate_project_like(project, user)
    with transaction.atomic():
        like, created = ProjectLike.objects.select_for_update().get_or_create(
            project=project,
            user=user,
        )
        if not created:
            like.delete()
        likes_count = ProjectLike.objects.filter(project=project).count()
    return {'liked': created, 'likes_count': likes_count}


def toggle_project_favorite(project: Project, user: User) -> dict:
    """Переключает состояние «в избранном» для проекта указанным пользователем.

    Если запись уже существует — удаляет (убирает из избранного).
    Если отсутствует — создаёт (добавляет в избранное).

    Возвращает словарь:
      - `favorited`: bool — стало ли проект в избранном после действия
    """
    validate_project_favorite(project, user)
    with transaction.atomic():
        favorite, created = (
            ProjectFavorite.objects.select_for_update().get_or_create(
                project=project, user=user
            )
        )
        if not created:
            favorite.delete()
            favorited = False
        else:
            favorited = True
    return {'favorited': favorited}
