from datetime import timedelta
from typing import Any

import django_filters
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import (
    Count,
    DurationField,
    F,
    Q,
    QuerySet,
)
from django.db.models.expressions import ExpressionWrapper
from rest_framework import serializers

from core.constants.projects import (
    BLOCKED,
    MAX_FILTER_DAYS,
    MEMBER,
    MIN_FILTER_DAYS,
    PUBLISHED,
    RECRUITING_CLOSED,
)
from projects.models import Project

User = get_user_model()


class ProjectOrderingFilter(django_filters.OrderingFilter):
    """Кастомный OrderingFilter для сортировки проектов.

    Поддерживает:
        - published_at — по дате публикации (по умолчанию, по убыванию)
        - like — по количеству лайков (по убыванию)
        - relevance — по релевантности полнотекстового поиска
          (только при наличии search в query_params)

    Использует query-параметр 'sort_by' (не 'ordering').
    """

    ordering_param = 'sort_by'

    def filter(self, qs: QuerySet, value: Any) -> QuerySet:
        """Применяет сортировку с поддержкой кастомных аннотаций."""
        if not value:
            return qs.order_by('-published_at')

        # Определяем, какие сортировки запрошены
        ordering = []
        for param in value:
            desc = param.startswith('-')
            field_name = param.lstrip('-')

            if field_name == 'like':
                # Аннотация likes_count уже добавлена в
                # get_optimized_project_queryset. Если её нет
                # (например, при прямом использовании фильтра без селектора),
                # добавляем.
                if 'likes_count' not in qs.query.annotations:
                    qs = qs.annotate(likes_count=Count('likes'))
                ordering.append('-likes_count' if desc else 'likes_count')
            elif field_name == 'relevance':
                search_query = self.parent.request.GET.get('search', '')
                if search_query:
                    search_vector = SearchVector(
                        'title', weight='A',
                    ) + SearchVector(
                        'short_desc', weight='B',
                    )
                    qs = qs.annotate(
                        search=search_vector,
                        rank=SearchRank(search_vector, search_query),
                    )
                    ordering.append('-rank' if desc else 'rank')
                else:
                    suffix = 'published_at'
                    ordering.append(f'-{suffix}' if desc else suffix)
            else:
                ordering.append(param)

        return qs.order_by(*ordering)


class ProjectFilter(django_filters.FilterSet):
    """Фильтр для проектов.

    Используется для списка проектов.
    - Ищем по форматам работы.
    - Ищем по навыкам.
    - Ищем по специализациям.
    - Фильтруем по длительности проекта в днях.
    - Поиск по названию, описанию.
    - Фильтр по статусу.
    - Показывает мои проекты, но с учётом роли юзера.
    - Сортировка через OrderingFilter.

    Исключение статусов (DRAFT, BLOCKED, ARCHIVED) для list
    выполняется в ProjectViewSet.get_queryset.
    """

    format_id = django_filters.BaseInFilter(
        field_name='project_format__format_id',
    )
    spec_id = django_filters.BaseInFilter(
        field_name='specializations__spec_id',
    )
    skills_id = django_filters.BaseInFilter(
        field_name='skills__skill_id',
    )
    # Фильтруем по дням
    duration_min = django_filters.NumberFilter(method='filter_duration')
    duration_max = django_filters.NumberFilter(method='filter_duration')
    duration_operator = django_filters.ChoiceFilter(
        choices=(
            ('less', 'Меньше'),
            ('greater', 'Больше'),
            ('between', 'Между'),
        ),
        method='filter_duration',
    )
    # Поиск по названию, описанию
    search = django_filters.CharFilter(method='filter_search')
    # Фильтр по статусу
    status = django_filters.BaseInFilter(field_name='status_project')
    # Показывает мои проекты, но с условием!
    my_project = django_filters.BooleanFilter(method='filter_my_project')
    # Сортировка
    sort_by = ProjectOrderingFilter(
        fields=(
            ('published_at', 'published_at'),
            ('like', 'like'),
            ('relevance', 'relevance'),
        ),
        field_labels={
            'published_at': 'По дате публикации',
            'like': 'По количеству лайков',
            'relevance': 'По релевантности',
        },
        label='Сортировка',
    )

    class Meta:
        model = Project
        fields = ()

    def filter_search(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Поиск по названию, описанию проекта."""
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) |
            Q(short_desc__icontains=value) |
            Q(full_desc__icontains=value),
        )

    def filter_duration(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Фильтрация проектов по длительности в днях.

        Длительность вычисляется как разница end_date - start_date.
        Для сравнения дни конвертируются в timedelta.

        Параметры (из query params):
            duration_min (int): Мин. длительность (7-365)
            duration_max (int): Макс. длительность (7-365)
            duration_operator (str): less | greater | between

        Логика:
            less    — duration <= duration_min
            greater — duration >= duration_min
            between — duration_min <= duration <= duration_max
        """
        duration_min = self.request.GET.get('duration_min')
        duration_max = self.request.GET.get('duration_max')
        operator = self.request.GET.get(
            'duration_operator', 'between',
        )
        if not duration_min and not duration_max:
            return queryset
        # Валидация входных данных
        try:
            min_days = (
                int(duration_min) if duration_min else MIN_FILTER_DAYS
            )
            max_days = (
                int(duration_max) if duration_max else MAX_FILTER_DAYS
            )
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                'Параметры duration_min и duration_max '
                'должны быть целыми числами.',
            )
        # Конвертируем дни в timedelta для сравнения interval с interval
        min_delta = timedelta(days=min_days)
        max_delta = timedelta(days=max_days)
        # Длительность проекта как interval (end_date - start_date)
        duration_expr = ExpressionWrapper(
            F('end_date') - F('start_date'),
            output_field=DurationField(),
        )
        queryset = queryset.annotate(duration=duration_expr)
        if operator == 'less':
            return queryset.filter(duration__lte=min_delta)
        if operator == 'greater':
            return queryset.filter(duration__gte=min_delta)
        # between (по умолчанию)
        return queryset.filter(
            duration__gte=min_delta,
            duration__lte=max_delta,
        )

    def filter_my_project(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Фильтрует проекты, где пользователь — автор или участник.

        - Наниматель (employer): возвращаются его проекты
          (за исключением blocked).
        - Работник (worker): возвращаются проекты, где он участник,
          со статусом published или recruiting_closed.
        - Админам и суперюзеру видно всё.
        """
        if not value or value == 'false':
            return queryset
        user = self.request.user
        if user.is_superuser or user.is_staff or user.role == 'admin':
            return queryset

        if user.projects_relation == User.ProjectsRelationChoices.EMPLOYER:
            # Наниматель — свои проекты (кроме blocked)
            return queryset.filter(
                author=user,
            ).exclude(status_project=BLOCKED)

        # Работник — проекты, где он участник
        return queryset.filter(
            participants__user=user,
            participants__status_participant=MEMBER,
            status_project__in=(PUBLISHED, RECRUITING_CLOSED),
        )
