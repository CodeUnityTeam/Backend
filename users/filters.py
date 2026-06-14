from typing import Any
import django_filters
from django.db.models import Q, QuerySet


class UserFilter(django_filters.FilterSet):
    """Фильтр профилей соискателей.

    Валидирует параметры. Фильтрация m2m связей и сортировка
    делегированы слою селекторов, чтобы избежать сброса порядка.
    """

    skill_ids: django_filters.CharFilter = django_filters.CharFilter(
        method='filter_noop'
    )
    spec_ids: django_filters.CharFilter = django_filters.CharFilter(
        method='filter_noop'
    )
    format_ids: django_filters.CharFilter = django_filters.CharFilter(
        method='filter_noop'
    )
    search: django_filters.CharFilter = django_filters.CharFilter(
        method='filter_by_search',
        help_text='Поиск по частичному совпадению ФИО, страны и города',
    )
    responses: django_filters.BooleanFilter = (
        django_filters.BooleanFilter(method='filter_noop')
    )
    sort_by: django_filters.CharFilter = django_filters.CharFilter(
        method='filter_noop'
    )

    class Meta:
        fields = []

    def _get_prefix(self, queryset: QuerySet[Any]) -> str:
        """Определяет префикс пути в зависимости от модели QuerySet."""
        return 'user__' if queryset.model.__name__ == 'Response' else ''

    def filter_by_search(
        self, queryset: QuerySet[Any], name: str, value: Any
    ) -> QuerySet[Any]:
        """Ищет по вхождению подстроки (icontains) в 4 текстовых поля."""
        if not value:
            return queryset

        pfx: str = self._get_prefix(queryset)
        return queryset.filter(
            Q(**{f'{pfx}first_name__icontains': value})
            | Q(**{f'{pfx}last_name__icontains': value})
            | Q(**{f'{pfx}country__icontains': value})
            | Q(**{f'{pfx}city__icontains': value})
        ).distinct()

    def filter_noop(
        self, queryset: QuerySet[Any], name: str, value: Any
    ) -> QuerySet[Any]:
        """Заглушка. Параметры обрабатываются на уровне селектора."""
        return queryset
