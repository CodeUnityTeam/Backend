# ruff: noqa

from types import SimpleNamespace

import pytest
from django.http import QueryDict
from rest_framework.exceptions import PermissionDenied

from qna.views.question import (
    QuestionViewSet,
    _build_question_list_cache_key,
)


def _request(*, authenticated: bool, query: str):
    return SimpleNamespace(
        user=SimpleNamespace(
            pk='viewer-id' if authenticated else None,
            is_authenticated=authenticated,
        ),
        query_params=QueryDict(query),
    )


def test_public_question_ids_key_is_shared_with_anonymous_viewer():
    authenticated = _request(authenticated=True, query='filter=popular')
    anonymous = _request(authenticated=False, query='filter=popular')

    assert _build_question_list_cache_key(authenticated) == (
        _build_question_list_cache_key(anonymous)
    )


def test_my_questions_key_is_not_created_for_anonymous_viewer():
    anonymous = _request(authenticated=False, query='filter=my')

    assert _build_question_list_cache_key(anonymous) is None


def test_my_questions_key_is_isolated_by_viewer():
    first = _request(authenticated=True, query='filter=my')
    second = _request(authenticated=True, query='filter=my')
    second.user.pk = 'another-viewer-id'

    assert _build_question_list_cache_key(first) != (
        _build_question_list_cache_key(second)
    )


def test_anonymous_my_filter_is_rejected_before_cache_read(mocker):
    cache = mocker.patch('qna.views.question.cache')
    view = QuestionViewSet()

    with pytest.raises(PermissionDenied):
        view.list(_request(authenticated=False, query='filter=my'))

    cache.get.assert_not_called()


def test_question_list_cache_stores_only_ordered_ids(mocker):
    question_ids = ['first-question-id', 'second-question-id']
    queryset = mocker.MagicMock()
    queryset.values_list.return_value = question_ids
    view = QuestionViewSet()
    view.action = 'list'
    view.get_queryset = mocker.Mock(return_value=queryset)
    view.filter_queryset = mocker.Mock(return_value=queryset)
    view.paginate_queryset = mocker.Mock(return_value=[])
    view.get_paginated_response = mocker.Mock(return_value=[])
    view.get_serializer = mocker.Mock(
        return_value=SimpleNamespace(data=[]),
    )
    cache = mocker.patch('qna.views.question.cache')
    cache.get.return_value = None

    view.list(_request(authenticated=False, query='limit=20&offset=0'))

    _, cached_value = cache.set.call_args.args[:2]
    assert cached_value == question_ids
    assert cache.set.call_args.kwargs['timeout'] == 180
