from typing import Any, Dict

from django.core.paginator import InvalidPage
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.constants.projects import MAX_PAGE_SIZE, PAGE_SIZE
from core.paginations_mixins import CustomPaginationMixin


class CustomProjectPagination(CustomPaginationMixin, PageNumberPagination):
    """Кастомный пагинатор для проектов с форматом."""

    page_size = PAGE_SIZE
    page_size_query_param = 'limit'
    max_page_size = MAX_PAGE_SIZE

    def paginate_queryset(
        self,
        queryset: Any,
        request: Any,
        view: Any = None,
    ) -> list[Any] | None:
        """Возвращает 400, если клиент передал некорректный номер страницы."""
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(queryset, page_size)
        page_number = self.get_page_number(request, paginator)
        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            message = self.invalid_page_message.format(
                page_number=page_number,
                message=str(exc),
            )
            raise ValidationError({'page': message})

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        return list(self.page)


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
