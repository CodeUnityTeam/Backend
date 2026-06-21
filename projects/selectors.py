from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import (
    BooleanField,
    Count,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Value,
)

from core.constants.projects import (
    ARCHIVED,
    BLOCKED,
    DRAFT,
    PUBLISHED,
    RECRUITING_CLOSED,
)

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
      - participants_count через Count.
      - likes_count через Count.
    """
    qs = Project.objects.select_related(
        'author',
    ).prefetch_related(
        'skills',
        'specializations',
        'project_format',
        Prefetch(
            'participants',
            queryset=ProjectParticipant.objects.select_related('user'),
        ),
    ).annotate(
        participants_count=Count('participants'),
        likes_count=Count('likes'),
    )
    qs = _annotate_is_liked_by_me(qs, user)
    return _annotate_is_participant(qs, user)


def _annotate_is_participant(
    qs: QuerySet[Project],
    user: User | None,
) -> QuerySet[Project]:
    """Аннотирует queryset проектов полем is_participant.

    Добавляет булево поле is_participant через подзапрос Exists.
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

    Фильтрует отклики по текущему пользователю — worker видит только
    свои отклики и приглашения, где он является приглашённым.

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
    queryset = Response.objects.select_related(
        'project__author',
        'user',
    ).prefetch_related(
        'project__skills',
        'project__participants',
        'project__likes',
    ).filter(user=user)
    # Аннотация is_liked_by_me
    if user.is_authenticated:
        queryset = queryset.annotate(
            is_liked_by_me=Exists(
                ProjectLike.objects.filter(
                    user=user,
                    project=OuterRef('project__project_id'),
                ),
            ),
        )
    else:
        queryset = queryset.annotate(
            is_liked_by_me=Value(False, output_field=BooleanField()),
        )
    # Аннотация participants_count
    return queryset.annotate(
        participants_count=Count('project__participants'),
    )


def get_recommended_projects_queryset(user: User) -> QuerySet[Project]:
    """Формирует QuerySet проектов для рекомендаций пользователю.

    На основе навыков пользователя находит проекты со статусом PUBLISHED,
    сортирует по убыванию количества совпадающих навыков (релевантность).
    - Исключаются проекты, где пользователь является автором.
    - Исключаются проекты, где пользователь уже участник (любой статус).
    - Если у пользователя нет навыков — возвращается пустой QuerySet.

    Аннотирует:
      - relevance — количество совпадающих навыков
      - participants_count — количество участников
      - is_liked_by_me — лайкнул ли текущий пользователь проект
    """
    user_skill_ids = list(
        user.skills.values_list('skill_id', flat=True),
    )
    if not user_skill_ids:
        return Project.objects.none()
    qs = (
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
            participants_count=Count('participants'),
        )
        .exclude(author=user)
        .exclude(participants__user=user)
        .select_related('author')
        .prefetch_related('skills')
        .distinct()
    )
    qs = _annotate_is_liked_by_me(qs, user)
    return qs.order_by('-relevance')


def get_visible_projects_for_list(
    qs: QuerySet[Project],
) -> QuerySet[Project]:
    """Исключает черновики, заблокированные и архивные проекты.

    Используется в ProjectViewSet.get_queryset для action 'list',
    когда не запрошен фильтр my_project.
    """
    return qs.exclude(
        status_project__in=[DRAFT, BLOCKED, ARCHIVED],
    )


def get_visible_projects_for_retrieve(
    qs: QuerySet[Project],
    user: User,
) -> QuerySet[Project]:
    """Возвращает проекты, доступные пользователю для просмотра.

    - Employer видит свои проекты + опубликованные/с закрытым набором.
    - Остальные пользователи — только опубликованные/с закрытым набором.

    Используется в ProjectViewSet.get_queryset для action 'retrieve'.
    """
    if (
        user.is_authenticated
        and user.projects_relation
        == User.ProjectsRelationChoices.EMPLOYER
    ):
        return qs.filter(
            Q(author=user)
            | Q(status_project__in=[PUBLISHED, RECRUITING_CLOSED]),
        )
    return qs.filter(
        status_project__in=[PUBLISHED, RECRUITING_CLOSED],
    )


def get_project_for_response_queryset() -> QuerySet[Project]:
    """Оптимизированный queryset проекта для откликов/приглашений.

    Загружает author через select_related для валидации прав
    (project.author == user).

    Используется в ProjectResponseViewSet.get_queryset.
    """
    return Project.objects.select_related('author')


def get_response_for_status_update_queryset() -> QuerySet[Response]:
    """Оптимизированный queryset откликов для изменения статуса.

    Загружает project__author и user через select_related
    для валидации прав (project.author, user_response.user).

    Используется в ResponseStatusViewSet.get_queryset.
    """
    return Response.objects.select_related(
        'project__author',
        'user',
    )
