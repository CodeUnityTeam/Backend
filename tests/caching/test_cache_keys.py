# ruff: noqa

import uuid
from types import SimpleNamespace

import pytest
from django.http import QueryDict

from projects.views.project import (
    _build_list_cache_key,
    _build_recommendations_cache_key,
)
from projects.views.response_project import _build_response_feed_cache_key
from qna.views.question import _build_question_list_cache_key
from users.views.profile import _build_profile_list_cache_key


def _user(*, authenticated: bool = True):
    return SimpleNamespace(
        pk=uuid.uuid4(),
        is_authenticated=authenticated,
        projects_relation='worker',
    )


def _request(user, query: str):
    return SimpleNamespace(user=user, query_params=QueryDict(query))


@pytest.mark.parametrize(
    ('builder', 'first_query', 'second_query'),
    [
        (
            lambda request: _build_list_cache_key(
                'projects', request.user, request.query_params,
            ),
            'page=1&limit=10&status_project=published',
            'page=9&limit=50&status_project=published',
        ),
        (
            _build_recommendations_cache_key,
            'page=1&limit=10&ordering=-published_at',
            'page=2&limit=20&ordering=-published_at',
        ),
        (
            _build_response_feed_cache_key,
            'page=1&limit=10&status_resp=pending',
            'page=3&limit=100&status_resp=pending',
        ),
        (
            _build_profile_list_cache_key,
            'page=1&limit=10&city=Kazan',
            'page=7&limit=50&city=Kazan',
        ),
        (
            _build_question_list_cache_key,
            'limit=10&offset=0&filter=popular',
            'limit=50&offset=100&filter=popular',
        ),
    ],
)
def test_pagination_does_not_change_ordered_id_cache_key(
    builder,
    first_query,
    second_query,
):
    user = _user()

    assert builder(_request(user, first_query)) == builder(
        _request(user, second_query),
    )


@pytest.mark.parametrize(
    'builder',
    [
        lambda request: _build_list_cache_key(
            'projects', request.user, request.query_params,
        ),
        _build_recommendations_cache_key,
        _build_response_feed_cache_key,
        _build_profile_list_cache_key,
    ],
)
def test_personal_ordered_id_keys_are_isolated_by_user(builder):
    request_a = _request(_user(), 'ordering=-created_at')
    request_b = _request(_user(), 'ordering=-created_at')

    assert builder(request_a) != builder(request_b)


@pytest.mark.parametrize(
    'builder',
    [
        lambda request: _build_list_cache_key(
            'projects', request.user, request.query_params,
        ),
        _build_recommendations_cache_key,
        _build_response_feed_cache_key,
        _build_profile_list_cache_key,
        _build_question_list_cache_key,
    ],
)
def test_filter_change_produces_another_ordered_id_key(builder):
    user = _user()

    assert builder(_request(user, 'ordering=created_at')) != builder(
        _request(user, 'ordering=-created_at'),
    )


def test_public_question_list_key_is_shared_between_viewers():
    request_a = _request(_user(), 'filter=popular')
    request_b = _request(_user(), 'filter=popular')

    assert _build_question_list_cache_key(
        request_a,
    ) == _build_question_list_cache_key(request_b)


def test_my_questions_key_is_isolated_by_user():
    request_a = _request(_user(), 'filter=my')
    request_b = _request(_user(), 'filter=my')

    assert _build_question_list_cache_key(
        request_a,
    ) != _build_question_list_cache_key(request_b)


def test_anonymous_project_list_is_not_cached():
    user = _user(authenticated=False)

    assert _build_list_cache_key('projects', user, QueryDict('page=1')) is None


def test_repeated_query_values_are_part_of_the_key():
    user = _user()
    first = _request(user, 'tags=python&tags=django')
    second = _request(user, 'tags=python&tags=redis')

    assert _build_profile_list_cache_key(
        first,
    ) != _build_profile_list_cache_key(second)
