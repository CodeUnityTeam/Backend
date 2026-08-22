from typing import Any
from uuid import UUID

import django_filters
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError


class UUIDInFilter(django_filters.BaseInFilter):
    """Кастомный фильтр для фильтрации по UUID.

    Проверяет валидность UUID и игнорирует некорректные значения.
    Если все значения некорректные, возвращает пустой queryset.

    Логика фильтрации — «OR»: объект должен соответствовать хотя бы
    одному из переданных UUID.

    Параметр max_length ограничивает суммарную длину строки запроса
    (включая разделители-запятые). При превышении бросается
    ValidationError (400).
    """

    def __init__(
        self,
        *args: Any,
        max_length: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует фильтр.

        :max_length: Максимальная допустимая длина.
        Если None, ограничение не применяется.
        """
        self.max_length = max_length
        super().__init__(*args, **kwargs)

    def filter(self, qs: QuerySet, value: list[str] | None) -> QuerySet:
        """Фильтрует queryset по списку UUID (логика «OR»)."""
        if not value:
            return qs
        # Суммарная длина строки запроса (значения + разделители-запятые)
        total_length = sum(len(item) for item in value) + (len(value) - 1)
        if self.max_length is not None and total_length > self.max_length:
            raise ValidationError(
                f'Длина параметра "{self.field_name}" не должна превышать '
                f'{self.max_length} символов.',
            )
        valid_uuids = []
        for uuids_value in value:
            try:
                valid_uuids.append(UUID(uuids_value.strip()))
            except (ValueError, TypeError, AttributeError):
                pass
        if not valid_uuids:
            return qs.none()
        return qs.filter(**{f'{self.field_name}__in': valid_uuids}).distinct()
