from typing import Any, Callable, Union

from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from projects.models import Response as ProjectResponse
from users.models.users import User, UserLike


def get_employer_base_queryset(
    current_user: Any,
    outer_ref_field: str,
    field_prefix: str,
    sort_by: str,
    skill_ids: tuple[str, ...],
    spec_ids: tuple[str, ...],
    format_ids: tuple[str, ...],
    queryset: QuerySet[Any],
) -> QuerySet[Any]:
    """Универсальная аннотация, фильтрация и сортировка QuerySet."""
    # 1. Подзапросы подсчета релевантности
    sub_skills = (
        User.objects.filter(pk=OuterRef(outer_ref_field))
        .annotate(c=Count('skills', filter=Q(skills__in=skill_ids)))
        .values('c')
    )
    sub_specs = (
        User.objects.filter(pk=OuterRef(outer_ref_field))
        .annotate(
            c=Count('specializations', filter=Q(specializations__in=spec_ids)),
        )
        .values('c')
    )
    sub_formats = (
        User.objects.filter(pk=OuterRef(outer_ref_field))
        .annotate(
            c=Count('workformats', filter=Q(workformats__in=format_ids)),
        )
        .values('c')
    )

    # 2. Аннотация виртуальных колонок СУБД
    queryset = queryset.annotate(
        match_count=Coalesce(Subquery(sub_skills[:1]), 0)
        + Coalesce(Subquery(sub_specs[:1]), 0)
        + Coalesce(Subquery(sub_formats[:1]), 0),
        annotated_is_liked=Exists(
            UserLike.objects.filter(
                employer=current_user, worker_id=OuterRef(outer_ref_field),
            ),
        ),
        likes_count=Count(f'{field_prefix}employers_likes', distinct=True),
    )

    # 3. Фильтрация по match_count и стратегии сортировки
    if skill_ids or spec_ids or format_ids:
        queryset = queryset.filter(match_count__gt=0)

    if sort_by == 'relevance':
        queryset = queryset.order_by('-match_count', '-created_at')
    elif sort_by == 'popularity':
        queryset = queryset.order_by('-likes_count', '-created_at')
    else:
        queryset = queryset.order_by('-created_at')

    return queryset.prefetch_related(
        f'{field_prefix}skills',
        f'{field_prefix}specializations',
        f'{field_prefix}workformats',
        f'{field_prefix}experiences',
    )


# --- Специфичные легкие функции фильтрации сценариев ---

def _apply_all_scenario(
        queryset: QuerySet[User], current_user: Any) -> QuerySet[User]:
    """Сценарий 1: Возвращает исходный QuerySet пользователей."""
    return queryset


def _apply_favourites_scenario(
        queryset: QuerySet[User], current_user: Any) -> QuerySet[User]:
    """Сценарий 2: Фильтрует пользователей по лайкам текущего нанимателя."""
    return queryset.filter(employers_likes__employer=current_user)


def _apply_responses_scenario(
    queryset: QuerySet[ProjectResponse], current_user: User,
) -> QuerySet[ProjectResponse]:
    """Сценарий 3: Возвращает отклики на проекты текущего нанимателя."""
    return queryset


# Маппер сценариев: связывает строковый ключ с легкой функцией-фильтром
SCENARIO_MAPPER: dict[str, Callable[[QuerySet[Any], Any], QuerySet[Any]]] = {
    'all': _apply_all_scenario,
    'favourites': _apply_favourites_scenario,
    'responses': _apply_responses_scenario,
}


def get_employer_profiles_selector(
    scenario: str,
    current_user: Any,
    queryset: QuerySet[Any],
) -> Union[QuerySet[ProjectResponse], QuerySet[User]]:
    """Применяет к готовому базовому QuerySet логику выбранного сценария."""
    filter_func = SCENARIO_MAPPER.get(scenario, _apply_all_scenario)
    return filter_func(queryset, current_user)
