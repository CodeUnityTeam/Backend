from typing import Any, Dict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.constants.projects import MAX_PAGE_SIZE, PAGE_SIZE


class ProfileListPagination(PageNumberPagination):
    """Пагинатор соискателей под логику кнопок 'Загрузить еще'."""

    page_query_param: str = 'page'
    page_size_query_param: str = 'limit'
    page_size: int = PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE

    def get_paginated_response(self, data: Any) -> Response:
        """Формирует ответ с порцией данных и номером следующей страницы."""
        total_count: int = self.page.paginator.count
        current_page: int = self.page.number
        current_limit: int = self.get_page_size(self.request)

        # Вычисляем полный физический остаток в базе
        total_remaining: int = total_count - (current_page * current_limit)

        # Вычисляем порцию для следующей загрузки
        if total_remaining <= 0:
            remaining: int = 0
        elif total_remaining < current_limit:
            remaining = total_remaining
        else:
            remaining = current_limit

        # Вычисляем номер следующей страницы
        next_page: int | None = (
            current_page + 1 if self.page.has_next() else None
        )

        return Response({
            'items': data,
            'total': total_count,
            'has_more': self.page.has_next(),
            'next_page': next_page,
            'remaining': remaining,
        })

    def get_paginated_response_schema(
        self,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Схема ответа для Swagger."""
        return {
            'type': 'object',
            'properties': {
                'items': schema,
                'total': {'type': 'integer'},
                'has_more': {'type': 'boolean'},
                'next_page': {
                    'type': 'integer',
                    'nullable': True,
                },
                'remaining': {'type': 'integer'},
            },
        }
