from datetime import timedelta
from typing import Any, List

import django_filters
from django.contrib.auth import get_user_model
from django.db.models import (
    Case,
    Count,
    DurationField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Value,
    When,
)
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated

from core.constants.projects import (
    ARCHIVED,
    BLOCKED,
    MAX_FILTER_DAYS,
    MEMBER,
    MIN_FILTER_DAYS,
    PUBLISHED,
    RECRUITING_CLOSED,
)
from core.filters import UUIDInFilter
from projects.models import Project, ProjectFavorite

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

    def filter(self, queryset: QuerySet, value: Any) -> QuerySet:
        """Применяет сортировку с поддержкой кастомных аннотаций."""
        if not value:
            return queryset.order_by('-published_at')

        ordering: List[str] = []
        param_list: List[str] = [str(param) for param in value]

        for param in param_list:
            desc: bool = param.startswith('-')
            field_name: str = param.lstrip('-')

            if field_name == 'published_at':
                ordering.append(
                    'published_at' if desc else '-published_at',
                )

            elif field_name == 'like':
                if 'likes_count' not in queryset.query.annotations:
                    queryset = queryset.annotate(
                        likes_count=Coalesce(
                            Count('likes'),
                            Value(0),
                        ),
                    )
                ordering.append(
                    'likes_count' if desc else '-likes_count',
                )

            elif field_name == 'relevance':
                request_object: Any = self.parent.request
                search_query: str = str(
                    request_object.GET.get('search', ''),
                )

                if len(search_query) > 0:
                    relevance_weight: Case = Case(
                        When(
                            title__iexact=search_query,
                            then=Value(4),
                        ),
                        When(
                            title__istartswith=search_query,
                            then=Value(3),
                        ),
                        When(
                            title__icontains=search_query,
                            then=Value(2),
                        ),
                        When(
                            Q(short_desc__icontains=search_query)
                            | Q(full_desc__icontains=search_query),
                            then=Value(1),
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    queryset = queryset.annotate(
                        relevance_score=relevance_weight,
                    )
                    ordering.extend(
                        ['-relevance_score', '-published_at'],
                    )
                else:
                    ordering.append(
                        'published_at' if desc else '-published_at',
                    )
            else:
                ordering.append(param)

        ordering.append('-project_id')
        return queryset.order_by(*ordering)


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
    - Показать избранные проекты (только worker'у)
    - Сортировка через OrderingFilter.

    Исключение статусов (DRAFT, BLOCKED, ARCHIVED) для list
    выполняется в ProjectViewSet.get_queryset.
    """

    format_id = UUIDInFilter(
        field_name='project_format__format_id',
    )
    spec_id = UUIDInFilter(
        field_name='specializations__spec_id',
    )
    skills_id = UUIDInFilter(
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
    my_project = django_filters.CharFilter(method='filter_my_project')
    # Показать избранные проекты
    favourites = django_filters.CharFilter(method='filter_favourites')
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

    def _parse_boolean_param(
        self,
        param_name: str,
        value: str | None,
    ) -> bool | None:
        """Валидирует булевый query-параметр и возвращает его значение.

        Возвращает:
            None — параметр не передан;
            True — параметр равен 'true';
            False — параметр равен 'false' (фильтрация не требуется).

        Для любого другого значения бросает ValidationError (400).
        NotAuthenticated (401) бросается только для значения 'true'
        у неаутентифицированного пользователя.
        """
        if not value:
            return None
        normalized = value.lower()
        if normalized not in ('true', 'false'):
            raise serializers.ValidationError(
                f'Недопустимое значение для параметра "{param_name}": '
                f'"{value}". Допустимые значения: True, False.',
            )
        if normalized == 'false':
            return False
        if not self.request.user.is_authenticated:
            raise NotAuthenticated()
        return True

    def filter_my_project(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Фильтрует проекты, где пользователь — автор или участник.

        - Наниматель (employer): возвращаются его проекты
          (за исключением archived, blocked).
        - Работник (worker): возвращаются проекты, где он участник,
          со статусом published или recruiting_closed.
        - Админам и суперюзеру видно всё.

        Параметр my_project:
        - Не передан → все проекты
        - 'false' → все проекты
        - 'true' → фильтрация по пользователю
        - Любое другое значение → 400 Bad Request
        """
        if not self._parse_boolean_param('my_project', value):
            return queryset
        user = self.request.user
        if (
            user.is_superuser
            or user.is_staff
            or user.role == User.RoleChoices.ADMIN
        ):
            return queryset
        if user.projects_relation == User.ProjectsRelationChoices.EMPLOYER:
            # Наниматель — свои проекты (кроме archived, blocked)
            return queryset.filter(
                author=user,
            ).exclude(status_project__in=(ARCHIVED, BLOCKED))

        # Работник — проекты, где он участник
        return queryset.filter(
            participants__user=user,
            participants__status_participant=MEMBER,
            status_project__in=(PUBLISHED, RECRUITING_CLOSED),
        )

    def filter_favourites(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Фильтрует проекты, добавленные текущим пользователем в избранное.

        Доступ только для worker.
        Анониму вернутся пустой queryset.

        Параметр favourites:
        - Не передан → все проекты
        - 'false' → все проекты
        - 'true' → фильтрация по избранному
        - Любое другое значение → 400 Bad Request
        """
        if not self._parse_boolean_param('favourites', value):
            return queryset
        user = self.request.user
        return queryset.filter(
            Exists(
                ProjectFavorite.objects.filter(
                    user=user,
                    project=OuterRef('project_id'),
                ),
            ),
        )
