from typing import Any, Dict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.constants.projects import MAX_PAGE_SIZE, PAGE_SIZE
from core.paginations_mixins import CustomPaginationMixin


class CustomProjectPagination(CustomPaginationMixin, PageNumberPagination):
    """Кастомный пагинатор для проектов с форматом."""

    page_size = PAGE_SIZE
    page_size_query_param = 'limit'
    max_page_size = MAX_PAGE_SIZE


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

    def get_paginated_response_schema(
        self,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Схема ответа для Swagger."""
        base_schema = super().get_paginated_response_schema(schema)
        base_schema['properties'].update({
            'page': {'type': 'integer'},
            'limit': {'type': 'integer'},
            'applied_filters': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'enum': [
                            'all', 'published', 'recruiting_closed',
                        ],
                    },
                },
            },
        })
        return base_schema
