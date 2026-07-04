from uuid import UUID

import django_filters
from django.db.models import Count, QuerySet


class UUIDInFilter(django_filters.BaseInFilter):
    """Кастомный фильтр для фильтрации по UUID.

    Проверяет валидность UUID и игнорирует некорректные значения.
    Если все значения некорректные, возвращает пустой queryset.
    """

    def filter(self, qs: QuerySet, value: list[str] | None) -> QuerySet:
        """Фильтрует queryset по списку UUID."""
        if not value:
            return qs
        valid_uuids = []
        for uuids_value in value:
            try:
                valid_uuids.append(UUID(uuids_value.strip()))
            except (ValueError, TypeError, AttributeError):
                pass
        if not valid_uuids:
            return qs.none()
        return (
            qs.filter(**{f'{self.field_name}__in': valid_uuids})
            .annotate(_match_count=Count(self.field_name, distinct=True))
            .filter(_match_count=len(valid_uuids))
            .distinct()
        )
