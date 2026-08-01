# ruff: noqa

from types import SimpleNamespace
from uuid import uuid4

from django.http import QueryDict

from projects.views.project import _build_list_cache_key


def _user():
    return SimpleNamespace(pk=uuid4(), is_authenticated=True)


def test_project_list_key_ignores_pagination_but_keeps_filters():
    """Одна выборка фильтров использует общий ключ для всех страниц."""
    user = _user()

    first_page = _build_list_cache_key(
        'projects',
        user,
        QueryDict('page=1&limit=10&ordering=-published_at'),
    )
    second_page = _build_list_cache_key(
        'projects',
        user,
        QueryDict('page=2&limit=50&ordering=-published_at'),
    )
    another_filter = _build_list_cache_key(
        'projects',
        user,
        QueryDict('page=1&limit=10&ordering=published_at'),
    )

    assert first_page == second_page
    assert first_page != another_filter
