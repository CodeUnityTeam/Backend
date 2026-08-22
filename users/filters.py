from typing import Any

import django_filters
from django.core.validators import MaxLengthValidator
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError


class StrictDjangoFilterBackend(DjangoFilterBackend):
    """Кастомный бэкенд фильтрации для валидации query-параметров.

    Обеспечивает сквозную проверку входящих данных на основе правил FilterSet
    и генерирует исключение ValidationError (400 Bad Request) при обнаружении
     ошибок.
    """

    def filter_queryset(self, request, queryset, view):
        filterset_class = self.get_filterset_class(view, queryset)

        if filterset_class:
            kwargs = self.get_filterset_kwargs(request, queryset, view)
            filterset = filterset_class(**kwargs)

            # Django-filter сам прогонит все параметры через форму,
            # проверит типы данных, max_length, min_length и соберет ошибки.
            if not filterset.is_valid():
                raise ValidationError(filterset.errors)  # 400 Bad Request

            return filterset.qs

        return queryset


class UserFilter(django_filters.FilterSet):
    """Фильтр профилей соискателей.

    Валидирует параметры. Фильтрация m2m связей и сортировка
    делегированы слою селекторов, чтобы избежать сброса порядка.
    """

    skill_ids = django_filters.CharFilter(
        method='filter_noop',
        validators=[MaxLengthValidator(2000)],
    )
    spec_ids = django_filters.CharFilter(
        method='filter_noop',
        validators=[MaxLengthValidator(500)],
    )
    format_ids = django_filters.CharFilter(
        method='filter_noop',
        validators=[MaxLengthValidator(200)],
    )
    search = django_filters.CharFilter(
        method='filter_by_search',
        validators=[MaxLengthValidator(100)],  # Жесткий лимит на поиск
        help_text='Поиск по частичному совпадению ФИО, страны и города',
    )
    responses: django_filters.BooleanFilter = (
        django_filters.BooleanFilter(method='filter_noop')
    )
    sort_by: django_filters.CharFilter = django_filters.CharFilter(
        method='filter_noop',
    )

    class Meta:
        fields = ()

    def _get_prefix(self, queryset: QuerySet[Any]) -> str:
        """Определяет префикс пути в зависимости от модели QuerySet."""
        return 'user__' if queryset.model.__name__ == 'Response' else ''

    def filter_by_search(
        self, queryset: QuerySet[Any], _name: str, value: Any,
    ) -> QuerySet[Any]:
        """Ищет по вхождению подстроки (icontains) в 4 текстовых поля."""
        if not value:
            return queryset

        pfx: str = self._get_prefix(queryset)
        return queryset.filter(
            Q(**{f'{pfx}first_name__icontains': value})
            | Q(**{f'{pfx}last_name__icontains': value})
            | Q(**{f'{pfx}country__icontains': value})
            | Q(**{f'{pfx}city__icontains': value}),
        ).distinct()

    def filter_noop(
        self, queryset: QuerySet[Any], _name: str, _value: Any,
    ) -> QuerySet[Any]:
        """Заглушка. Параметры обрабатываются на уровне селектора."""
        return queryset
