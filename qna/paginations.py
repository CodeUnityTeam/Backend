
from rest_framework.pagination import LimitOffsetPagination

from core.constants.qna import LIMIT_QNA_MAX, LIMIT_QNA_MIN
from core.paginations_mixins import CustomPaginationMixin


class CustomQuestionOffsetPagination(
    CustomPaginationMixin,
    LimitOffsetPagination,
):
    """Кастомный пагинатор для вопросов."""

    default_limit = LIMIT_QNA_MIN
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = LIMIT_QNA_MAX
