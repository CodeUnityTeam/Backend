from typing import Any, Optional

import django_filters
from django.db.models import F, Q, QuerySet
from rest_framework.request import Request

from core.constants.projects import (
    APPROVED,
    MAX_FILTER_DAYS,
    MIN_FILTER_DAYS,
    PENDING,
    REJECTED,
    WITHDRAWN,
)

from .models import Project, Response


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
        return queryset.filter(
            Q(title__icontains=value) |
            Q(short_desc__icontains=value) |
            Q(full_desc__icontains=value),
        )

    # TODO [PROJECTS]: Заменить ручную filter_duration на стандартный
    #   django-filter NumberFilter с DurationExpression.
    #   Проблема: filter_duration (строка 76) вручную:
    #     1. Извлекает duration_min, duration_max, duration_operator из self.data.
    #     2. Вычисляет длительность через F('end_date') - F('start_date').
    #     3. Применяет фильтр в зависимости от оператора.
    #   Это можно заменить на декларативный подход через аннотацию в queryset
    #   и стандартные NumberFilter с lookup_expr.
    #
    #   Решение через стандартный django-filter:
    #   1. Добавить аннотацию duration в get_optimized_project_queryset:
    #      from django.db.models import F, DurationField, ExpressionWrapper
    #
    #      def get_optimized_project_queryset():
    #          return Project.objects.annotate(
    #              duration=ExpressionWrapper(
    #                  F('end_date') - F('start_date'),
    #                  output_field=DurationField(),
    #              ),
    #          ).select_related('author').prefetch_related(...)
    #
    #   2. В ProjectFilter заменить кастомный метод на стандартные фильтры:
    #      from django_filters import NumberFilter, DurationFilter
    #
    #      class ProjectFilter(django_filters.FilterSet):
    #          duration_min = NumberFilter(
    #              field_name='duration',
    #              lookup_expr='gte',
    #              label='Минимальная длительность (дни)',
    #          )
    #          duration_max = NumberFilter(
    #              field_name='duration',
    #              lookup_expr='lte',
    #              label='Максимальная длительность (дни)',
    #          )
    #
    #   3. Если нужен оператор 'less'/'greater'/'between' — использовать
    #      RangeFilter или кастомный метод, но с использованием
    #      DurationField для конвертации дней в timedelta:
    #
    #      from django.utils import timezone
    #      from datetime import timedelta
    #
    #      duration_range = django_filters.RangeFilter(
    #          field_name='duration',
    #          label='Диапазон длительности',
    #          method='filter_duration_range',
    #      )
    #
    #      def filter_duration_range(self, queryset, name, value):
    #          if value.start:
    #              queryset = queryset.filter(
    #                  duration__gte=timedelta(days=value.start),
    #              )
    #          if value.stop:
    #              queryset = queryset.filter(
    #                  duration__lte=timedelta(days=value.stop),
    #              )
    #          return queryset
    #
    #   Преимущества:
    #     - Декларативное описание фильтров через field_name и lookup_expr.
    #     - Аннотация duration вычисляется один раз в queryset, а не в каждом filter().
    #     - DurationField корректно работает с интервалами PostgreSQL.
    #     - RangeFilter автоматически парсит min/max из query-параметров.
    #     - Убирается ручное извлечение self.data.get().
    def filter_duration(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Фильтрация проектов по длительности в днях."""
        duration_min = self.data.get('duration_min')
        duration_max = self.data.get('duration_max')
        operator = self.data.get('duration_operator', 'between')
        if not duration_min and not duration_max:
            return queryset
        # Преобразуем в числа с дефолтными значениями
        min_days = int(duration_min) if duration_min else MIN_FILTER_DAYS
        max_days = int(duration_max) if duration_max else MAX_FILTER_DAYS
        # Вычисляем длительность как разницу между датами
        duration_expr = F('end_date') - F('start_date')
        if operator == 'less':
            # Длительность меньше или равна min_days
            return queryset.annotate(
                duration=duration_expr,
            ).filter(duration__lte=min_days)
        if operator == 'greater':
            # Длительность больше или равна max_days
            return queryset.annotate(
                duration=duration_expr,
            ).filter(duration__gte=max_days)
        # Длительность между min_days и max_days
        return queryset.annotate(duration=duration_expr).filter(
            duration__range=(min_days, max_days),
        )

    # TODO [PROJECTS]: Обращение к 'status' вместо 'status_project' в filter_my_project.
    #   В модели Project поле называется status_project (models.py:143),
    #   но в filter_my_project используется:
    #   - .exclude(status='archived') (строка 128)
    #   - status__in=['published', 'recruiting_closed'] (строка 132)
    #   Должно быть status_project='archived' и status_project__in=[...].
    #   Из-за этого фильтрация my_project не работает корректно.
    # TODO [PROJECTS]: hasattr(user, 'author_projects') и hasattr(user, 'participant_projects')
    #   всегда вернут True, т.к. это related_name (строка 128-129).
    #   Логика не разделяет автора и участника — оба условия истинны.
    #   Нужно проверять через user.projects.exists() (автор) или
    #   user.project_participations.exists() (участник).
    def filter_my_project(
        self,
        queryset: QuerySet[Project],
        name: str,
        value: str | None,
    ) -> QuerySet[Project]:
        """Фильтрует проекты, где пользователь — автор или участник.

        - Если пользователь — автор: возвращаются все проекты
        (за исключением archived).
        - Если пользователь — участник: возвращаются только проекты со статусом
        published или recruiting_closed.
        - Админам и суперюзеру видно всё.
        """
        if not value:
            return queryset
        user = self.request.user
        if user.is_superuser or user.is_staff or user.role == 'admin':
            return queryset
        if hasattr(user, 'author_projects'):
            return queryset.filter(author=user).exclude(status='archived')
        if hasattr(user, 'participant_projects'):
            return queryset.filter(
                participants=user,
                status__in=['published', 'recruiting_closed'],
            )
        return queryset


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
