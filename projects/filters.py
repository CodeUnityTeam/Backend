import django_filters
from django.db.models import F, Q, QuerySet

from core.constants.projects import MAX_FILTER_DAYS, MIN_FILTER_DAYS

from .models import Project


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
