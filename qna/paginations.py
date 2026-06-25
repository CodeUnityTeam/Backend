from typing import Any

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from core.constants.qna import LIMIT_QNA_MAX, LIMIT_QNA_MIN


class CustomQuestionOffsetPagination(LimitOffsetPagination):
    """Кастомный пагинатор для вопросов."""

    default_limit = LIMIT_QNA_MIN
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = LIMIT_QNA_MAX

    def get_paginated_response(self, data: Any) -> Response:
        """Формируем ответ для списка проектов."""
        return Response({
            'items': data,
            'total': self.count,
            'has_more': ((self.offset + self.limit) < self.count),
        })
