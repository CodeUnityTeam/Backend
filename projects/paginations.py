from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.constants.projects import (
    MAX_PAGE_SIZE,
    PAGE_SIZE,
    PAGE_SIZE_QUERY_PARAM,
)


class CustomProjectPagination(PageNumberPagination):
    """Кастомный пагинатор для проектов с форматом."""

    page_size = PAGE_SIZE
    page_size_query_param = PAGE_SIZE_QUERY_PARAM
    max_page_size = MAX_PAGE_SIZE

    def get_paginated_response(self, data: Any) -> Response:
        """Формируем ответ для списка проектов."""
        return Response({
            'items': data,
            'total': self.page.paginator.count,
            'has_more': self.page.has_next(),
        })
