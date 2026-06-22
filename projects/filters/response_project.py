
from typing import Any, Optional

import django_filters
from django.contrib.auth import get_user_model
from django.db.models import (
    QuerySet,
)
from rest_framework.request import Request

from core.constants.projects import (
    APPROVED,
    PENDING,
    REJECTED,
    WITHDRAWN,
)
from projects.models import Response

User = get_user_model()


class ResponseFeedFilter(django_filters.FilterSet):
    """Фильтр для ленты откликов/приглашений.

    Доступен только для пользователей с ролью worker.
    По умолчанию отдаются все отклики (status=all).
    Сортировка по created_at (по умолчанию desc).
    """

    status = django_filters.CharFilter(
        method='filter_status',
        label='Статус отклика',
    )
    project_id = django_filters.UUIDFilter(
        field_name='project__project_id',
        label='Фильтр по проекту',
    )
    sort_order = django_filters.CharFilter(
        method='filter_sort_order',
        label='Порядок сортировки (asc/desc, по умолчанию desc)',
    )

    class Meta:
        model = Response
        fields = ['status', 'project_id']

    def __init__(
        self,
        data: Optional[dict] = None,
        queryset: Optional[QuerySet] = None,
        request: Optional[Request] = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует фильтр с дополнительными параметрами.

        Если sort_order не передан — по умолчанию desc (новые сначала).
        """
        if data is not None and 'sort_order' not in data:
            data = data.copy()
            data['sort_order'] = 'desc'
        super().__init__(data, queryset, **kwargs)
        self.request = request

    def filter_status(
        self,
        queryset: QuerySet,
        name: str,
        status_resp: str,
    ) -> QuerySet:
        """Фильтрация по статусу отклика.

        Допустимые значения: all, pending, approved, rejected, withdrawn.
        - 'all' — возвращаются все отклики.
        - Если значение не входит в допустимые — пустой результат.
        """
        if status_resp == 'all':
            return queryset
        if status_resp not in {PENDING, APPROVED, REJECTED, WITHDRAWN}:
            return queryset.none()
        return queryset.filter(status_resp=status_resp)

    def filter_sort_order(
        self,
        queryset: QuerySet,
        name: str,
        value: str,
    ) -> QuerySet:
        """Сортировка по created_at.

        desc — новые сначала (по умолчанию), asc — старые сначала.
        """
        order_prefix = '-' if value == 'desc' else ''
        return queryset.order_by(f'{order_prefix}created_at')
