from rest_framework.pagination import PageNumberPagination


class ProfileListPagination(PageNumberPagination):
    """Кастомная пагинация для списка профилей."""

    page_query_param = 'page'
    page_size_query_param = 'limit'
    page_size = 20
    max_page_size = 100
