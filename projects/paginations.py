from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.constants.projects import MAX_PAGE_SIZE, PAGE_SIZE


class CustomProjectPagination(PageNumberPagination):
    """Кастомный пагинатор для проектов с форматом."""

    page_size = PAGE_SIZE
    page_size_query_param = 'limit'
    max_page_size = MAX_PAGE_SIZE

    def get_paginated_response(self, data: Any) -> Response:
        """Формируем ответ для списка проектов."""
        return Response({
            'items': data,
            'total': self.page.paginator.count,
            'has_more': self.page.has_next(),
        })


class CustomResponseFeedPagination(CustomProjectPagination):
    """Кастомный пагинатор для ленты откликов."""

    def get_paginated_response(self, data: Any) -> Response:
        """Формируем ответ для списка откликов (карточек проектов)."""
        base_response = super().get_paginated_response(data).data
        return Response({
            **base_response,
            'page': self.page.number,
            'limit': self.get_page_size(self.request),
            'applied_filters': {
                'status': self.request.query_params.get('status', 'all'),
            },
        })
