from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, QuerySet

from core.constants.projects import PENDING, PUBLISHED

from .models import Project, ProjectLike, Response

User = get_user_model()


def _annotate_is_liked_by_me(
    qs: QuerySet[Project],
    user: User | None,
) -> QuerySet[Project]:
    """Аннотирует queryset проектов полем is_liked_by_me.

    Добавляет булево поле is_liked_by_me на уровне БД через подзапрос Exists.
    Если user не передан или не аутентифицирован — аннотирует False.
    """
    if user is not None and user.is_authenticated:
        return qs.annotate(
            is_liked_by_me=Exists(
                ProjectLike.objects.filter(
                    user=user,
                    project=OuterRef('project_id'),
                ),
            ),
        )
    return qs.annotate(is_liked_by_me=Exists(ProjectLike.objects.none()))


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


def get_optimized_project_queryset(
    user: User | None = None,
) -> QuerySet[Project]:
    """Возвращает оптимизированный queryset проектов с связанными данными.

    Используется для list и retrieve запросов.
    Аннотирует is_liked_by_me через Exists-подзапрос для переданного user.
    """
    qs = Project.objects.select_related(
        'author',
    ).prefetch_related(
        'skills',
        'specializations',
        'project_format',
        'participants',
        'likes',
        'responses',
    )
    return _annotate_is_liked_by_me(qs, user)


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
