from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import (
    BooleanField,
    Count,
    Exists,
    OuterRef,
    Q,
    QuerySet,
    Value,
)

from core.constants.projects import PUBLISHED

from .models import Project, ProjectLike, ProjectParticipant, Response

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
    Аннотирует:
      - is_liked_by_me через Exists-подзапрос для переданного user.
      - is_participant через Exists-подзапрос членства в проекте.
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
    qs = _annotate_is_liked_by_me(qs, user)
    return _annotate_is_participant(qs, user)


def _annotate_is_participant(
    qs: QuerySet[Project],
    user: User | None,
) -> QuerySet[Project]:
    """Аннотирует queryset проектов полем is_participant.

    Добавляет булево поле is_participant на уровне БД через подзапрос Exists.
    Если user не передан или не аутентифицирован — аннотирует False.
    """
    if user is not None and user.is_authenticated:
        return qs.annotate(
            is_participant=Exists(
                ProjectParticipant.objects.filter(
                    project=OuterRef('project_id'),
                    user=user,
                ),
            ),
        )
    return qs.annotate(
        is_participant=Value(False, output_field=BooleanField()),
    )


def get_response_feed_queryset(user: User) -> QuerySet:
    """Возвращает базовый queryset для ленты откликов текущего пользователя.

    Аннотирует:
      - participants_count — количество участников проекта
      - is_liked_by_me — лайкнул ли текущий пользователь проект

    Оптимизация запросов:
      - select_related('project__author') — проект + автор одним join
      - prefetch_related('project__skills') — навыки проекта
      - prefetch_related('project__participants') — участники
      - prefetch_related('project__likes') — лайки (для is_liked_by_me)

    user (User): текущий пользователь
    QuerySet: отфильтрованный queryset откликов
    """
    qs = Response.objects.select_related(
        'project__author',
        'user',
    ).prefetch_related(
        'project__skills',
        'project__participants',
        'project__likes',
    )

    # Аннотация is_liked_by_me
    if user.is_authenticated:
        qs = qs.annotate(
            is_liked_by_me=Exists(
                ProjectLike.objects.filter(
                    user=user,
                    project=OuterRef('project_id'),
                ),
            ),
        )
    else:
        qs = qs.annotate(
            is_liked_by_me=Value(False, output_field=BooleanField()),
        )

    # Аннотация participants_count
    qs = qs.annotate(
        participants_count=Count('project__participants'),
    )

    return qs


def get_recommended_projects_queryset(user: User) -> QuerySet[Project]:
    """Формирует QuerySet проектов для рекомендаций пользователю.

    На основе навыков пользователя находит проекты со статусом PUBLISHED,
    сортирует по убыванию количества совпадающих навыков (релевантность).
    - Исключаются проекты, где пользователь является автором.
    - Исключаются проекты, где пользователь уже участник (любой статус).
    - Если у пользователя нет навыков — возвращается пустой QuerySet.
    """
    user_skill_ids = list(
        user.skills.values_list('skill_id', flat=True),
    )
    if not user_skill_ids:
        return Project.objects.none()
    return (
        Project.objects
        .filter(
            skills__skill_id__in=user_skill_ids,
            status_project=PUBLISHED,
        )
        .annotate(
            relevance=Count(
                'skills',
                filter=Q(skills__skill_id__in=user_skill_ids),
            ),
        )
        .exclude(author=user)
        .exclude(participants__user=user)
        .select_related('author')
        .prefetch_related(
            'skills',
            'participants',
            'likes',
        )
        .distinct()
        .order_by('-relevance')
    )
