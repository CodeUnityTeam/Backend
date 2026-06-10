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


# TODO [PROJECTS]: Дублирование applied_filters в CustomResponseFeedPagination.
#   Пагинатор (строка 39) добавляет applied_filters в ответ.
#   Но в responses_feed (views.py:705-708) applied_filters добавляются снова
#   для непагинированного ответа. При пагинации filters приходят из пагинатора,
#   при отсутствии пагинации — из views.py. Логика размазана по двум местам.
#   Решение: вынести добавление applied_filters только в пагинатор или только
#   в views.py, но не в оба места.
class CustomResponseFeedPagination(PageNumberPagination):
    """Кастомный пагинатор для рекомендованных проектов пользователю.

    В ответ включает примененные фильтры.
    """

    page_size = PAGE_SIZE
    page_size_query_param = 'limit'
    max_page_size = MAX_PAGE_SIZE

    def get_paginated_response(self, data: Any) -> Response:
        """Формируем ответ для рекомендаций (по проектам)."""
        return Response({
            'items': data,
            'total': self.page.paginator.count,
            'page': self.page.number,
            'limit': self.get_page_size(self.request),
            'has_more': self.page.has_next(),
            'applied_filters': {
                'card_type': self.request.query_params.get('card_type', 'all'),
                'status': self.request.query_params.get('status', 'all'),
            },
        })
