from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from core.constants.projects import PENDING, PUBLISHED

from .models import Project, Response

User = get_user_model()


def get_project_with_relations(project_id: UUID) -> Project:
    """Возвращает проект с загруженными связанными объектами.

    - author (через select_related)
    - skills, specializations, project_format (через prefetch_related)
    """
    return (
        Project.objects
        .select_related(
            'author',
        )
        .prefetch_related(
            'skills',
            'specializations',
            'project_format',
        )
        .get(project_id=project_id)
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


def get_response_feed_queryset(user: User) -> QuerySet:
    """Возвращает базовый queryset для ленты откликов текущего пользователя.

    user (User): текущий пользователь
    QuerySet: отфильтрованный queryset откликов
    """
    return Response.objects.select_related(
        'project',
        'user',
    ).order_by('-created_at')


def get_recommended_projects_queryset(user: User) -> QuerySet[Project]:
    """Формирует QuerySet проектов для рекомендаций пользователю.

    Формируется на основе скиллов пользователя, которые совпадают с скиллами,
    требуемыми для выполнения проекта.

    - Показываем проекты со статусом PUBLISHED.
    - Исключаем проекты пользователя.
     - Исключаем проекты, где пользователь уже участник.
    """
    user_skill_ids = [skill.skill_id for skill in user.skills.all()]
    if not user_skill_ids:
        return Project.objects.none()
    # queryset с подсчётом совпадающих навыков
    recommended = Project.objects.filter(
        skills__skill_id__in=user_skill_ids,
        status_project=PUBLISHED,
    ).distinct()
    return recommended.exclude(
        participants__user=user,
        participants__status_participant=PENDING,
    )
