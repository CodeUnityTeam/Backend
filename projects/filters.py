from datetime import timedelta
from typing import Any, Optional

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
from rest_framework.request import Request

from core.constants.projects import (
    APPROVED,
    BLOCKED,
    MAX_FILTER_DAYS,
    MIN_FILTER_DAYS,
    PENDING,
    PUBLISHED,
    RECRUITING_CLOSED,
    REJECTED,
    WITHDRAWN,
)

from .models import Project, Response

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
        choices=[
            ('less', 'Меньше'),
            ('greater', 'Больше'),
            ('between', 'Между'),
        ],
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
        fields = []

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
        if not value:
            return queryset
        user = self.request.user
        if user.is_superuser or user.is_staff or user.role == 'admin':
            return queryset

        if user.projects_relation == User.ProjectsRelationChoices.EMPLOYER:
            # Наниматель — свои проекты (кроме blocked)
            return queryset.filter(
                author=user,
            ).exclude(status_project=BLOCKED)

        # Работник — проекты, где он участник с APPROVED
        return queryset.filter(
            participants__user=user,
            participants__status_participant=APPROVED,
            status_project__in=[PUBLISHED, RECRUITING_CLOSED],
        )


class ResponseFeedFilter(django_filters.FilterSet):
    """Фильтр для ленты откликов."""

    status = django_filters.CharFilter(method='filter_status')
    card_type = django_filters.CharFilter(method='filter_card_type')
    project_id = django_filters.UUIDFilter(field_name='project__project_id')
    sort_by = django_filters.CharFilter(
        method='filter_sort_by',
        label='Поле сортировки',
    )
    sort_order = django_filters.ChoiceFilter(
        choices=[('asc', 'asc'), ('desc', 'desc')],
        label='Порядок сортировки',
    )

    class Meta:
        model = Response
        fields = ['card_type', 'status', 'project_id']

    def __init__(
        self,
        data: Optional[dict] = None,
        queryset: Optional[QuerySet] = None,
        request: Optional[Request] = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует фильтр с дополнительными параметрами."""
        super().__init__(data, queryset, **kwargs)
        self.request = request

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        """"Фильтруем QuerySet по времени создания."""
        queryset = super().filter_queryset(queryset)
        sort_by = self.data.get('sort_by', 'created_at')
        sort_order = self.data.get('sort_order', 'desc')
        order_prefix = '-' if sort_order == 'desc' else ''
        return queryset.order_by(f'{order_prefix}{sort_by}')

    def filter_status(
        self,
        queryset: QuerySet,
        name: str,
        status_resp: str,
    ) -> QuerySet:
        """Фильтрация по статусу отклика."""
        if status_resp == 'all' or status_resp not in [
            PENDING,
            APPROVED,
            REJECTED,
            WITHDRAWN,
        ]:
            return queryset
        return queryset.filter(status_resp=status_resp)

    def filter_card_type(
        self,
        queryset: QuerySet,
        name: str,
        value: Any,
    ) -> QuerySet:
        """Фильтрация по типу карточки."""
        if value not in ['all', 'project', 'profile']:
            return queryset
        if not hasattr(self.request, 'user'):
            return queryset.none()
        if not self.request.user or not self.request.user.is_authenticated:
            return queryset.none()
        user = self.request.user
        if value == 'all':
            return queryset
        if value == 'project':
            # Отклики, где пользователь — соискатель
            return queryset.filter(user=user)
        if value == 'profile':
            # Отклики на проекты пользователя (пользователь — автор проекта)
            return queryset.filter(project__author=user)
        return queryset.none()
