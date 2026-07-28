from typing import Any, Dict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPaginationMixin:
    """Миксин для кастомного формата пагинации.

    Вопросы, проекты и проекты для ленты откликов.
    """

    def get_paginated_response(self, data: Any) -> Response:
        """Возвращает items/total/has_more."""
        return Response({
            'items': data,
            'total': self.page.paginator.count if isinstance(
                self,
                PageNumberPagination,
            ) else self.count,
            'has_more': (
                self.page.has_next() if isinstance(self, PageNumberPagination)
                else ((self.offset + self.limit) < self.count)
            ),
        })

    def get_paginated_response_schema(
        self,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Ответ для схемы в документации."""
        return {
            'type': 'object',
            'properties': {
                'items': schema,
                'total': {'type': 'integer'},
                'has_more': {'type': 'boolean'},
            },
        }
