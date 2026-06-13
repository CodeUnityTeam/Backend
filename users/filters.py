from typing import Any

import django_filters
from django.db.models import QuerySet

from .models import User


class UUIDInFilter(
    django_filters.BaseInFilter, django_filters.UUIDFilter,
):
    """Фильтр для валидации и парсинга списка UUID через запятую."""

    pass


class UserFilter(django_filters.FilterSet):
    """Фильтр для поиска пользователей по m2m связям и откликам."""

    skill_ids: UUIDInFilter = UUIDInFilter(
        field_name='skills', lookup_expr='in',
    )
    spec_ids: UUIDInFilter = UUIDInFilter(
        field_name='specializations', lookup_expr='in',
    )
    format_ids: UUIDInFilter = UUIDInFilter(
        field_name='workformats', lookup_expr='in',
    )
    responses: django_filters.BooleanFilter = (
        django_filters.BooleanFilter(method='filter_responses')
    )

    class Meta:
        model = User
        fields = []

    def filter_responses(
        self, queryset: QuerySet[User], name: str, value: Any,
    ) -> QuerySet[User]:
        """Фильтрует пользователей по откликам на проекты автора."""
        if value is not True:
            return queryset

        user: Any = self.request.user
        if not user or user.is_anonymous:
            return queryset.none()

        return queryset.filter(responses__project__author=user).distinct()
