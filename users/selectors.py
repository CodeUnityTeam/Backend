from typing import Any, Union
from django.db.models import Count, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce
from projects.models import Response as ProjectResponse
from users.models.users import User


def get_employer_profiles_selector(
    current_user: Any,
    responses_param: str,
    sort_by: str,
    skill_ids: tuple[str, ...],
    spec_ids: tuple[str, ...],
    format_ids: tuple[str, ...],
) -> Union[QuerySet[ProjectResponse], QuerySet[User]]:
    """Формирует QuerySet соискателей/откликов без дублирования кода."""
    # Выбор базового queryset
    if responses_param == 'true':
        queryset: QuerySet[Any] = (
            ProjectResponse.objects.filter(project__author=current_user)
            .exclude(user=current_user)
            .select_related('project', 'user')
        )
        outer_ref_field: str = 'user_id'
        prefetch_prefix: str = 'user__'
    else:
        queryset = User.objects.exclude(pk=current_user.pk)
        outer_ref_field = 'pk'
        prefetch_prefix = ''

    # Подзапросы для подсчета количество совпавших фильтров
    sub_skills = (
        User.objects.filter(pk=OuterRef(outer_ref_field))
        .annotate(c=Count('skills', filter=Q(skills__in=skill_ids)))
        .values('c')
    )
    sub_specs = (
        User.objects.filter(pk=OuterRef(outer_ref_field))
        .annotate(
            c=Count(
                'specializations', filter=Q(specializations__in=spec_ids)
            )
        )
        .values('c')
    )
    sub_formats = (
        User.objects.filter(pk=OuterRef(outer_ref_field))
        .annotate(
            c=Count('workformats', filter=Q(workformats__in=format_ids))
        )
        .values('c')
    )

    # Аннотация, фильтрация и сортировка
    queryset = queryset.annotate(
        match_count=Coalesce(Subquery(sub_skills[:1]), 0)
        + Coalesce(Subquery(sub_specs[:1]), 0)
        + Coalesce(Subquery(sub_formats[:1]), 0)
    )

    if skill_ids or spec_ids or format_ids:
        queryset = queryset.filter(match_count__gt=0)

    if sort_by == 'relevance':
        queryset = queryset.order_by('-match_count', '-created_at')
    else:
        queryset = queryset.order_by('-created_at')

    return queryset.prefetch_related(
        f'{prefetch_prefix}skills',
        f'{prefetch_prefix}specializations',
        f'{prefetch_prefix}workformats',
        f'{prefetch_prefix}experiences',
    )
