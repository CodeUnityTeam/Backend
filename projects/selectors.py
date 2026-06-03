import uuid

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from core.constants.projects import APPLICANT, PENDING

from .models import Project, Response

User = get_user_model()


def get_project_or_404(project_id: str) -> Project:
    """Получает проект по ID или выбрасывает 404, если не найден."""
    return get_object_or_404(Project, project_id=project_id)


def get_project_with_relations(project_id: uuid) -> Project:
    """Возвращает проект с загруженными связанными объектами.

    - author (через select_related)
    - skills, specializations, project_format (через prefetch_related)
    """
    return Project.objects.select_related(
        'author',
    ).prefetch_related(
        'skills',
        'specializations',
        'project_format',
    ).get(project_id=project_id)


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


def get_optimized_project_queryset() -> QuerySet[Project]:
    """Возвращает оптимизированный queryset проектов с связанными данными."""
    return Project.objects.select_related(
        'author',
    ).prefetch_related(
        'skills',
        'specializations',
        'project_format',
        'participants',
        'likes',
        'responses',
    )
