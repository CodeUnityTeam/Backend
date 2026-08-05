# ruff: noqa

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.http import QueryDict
from rest_framework.response import Response

from core.cache_mixins import CacheRetrieveMixin, get_or_seed_counter
from core.constants.cache import (
    PROJECT_LIST_CACHE_TIMEOUT,
    QUESTION_LIST_CACHE_TIMEOUT,
    RESPONSE_FEED_CACHE_TIMEOUT,
    USER_PROFILE_LIST_CACHE_TIMEOUT,
)
from projects.views.project import ProjectViewSet
from projects.views.response_project import ResponseFeedViewSet
from qna.views.question import QuestionViewSet
from users.views.profile import UserProfileListView


def _request(query: str = ''):
    return SimpleNamespace(
        user=SimpleNamespace(
            pk=uuid.uuid4(),
            is_authenticated=True,
            projects_relation='worker',
        ),
        query_params=QueryDict(query),
    )


LIST_CASES = (
    (ProjectViewSet, 'projects.views.project.cache', 'project_id', PROJECT_LIST_CACHE_TIMEOUT),
    (QuestionViewSet, 'qna.views.question.cache', 'question_id', QUESTION_LIST_CACHE_TIMEOUT),
    (UserProfileListView, 'users.views.profile.cache', 'pk', USER_PROFILE_LIST_CACHE_TIMEOUT),
    (ResponseFeedViewSet, 'projects.views.response_project.cache', 'response_id', RESPONSE_FEED_CACHE_TIMEOUT),
)


@pytest.mark.parametrize(
    ('view_class', 'cache_path', 'id_field', 'timeout'),
    LIST_CASES,
)
def test_list_cache_miss_stores_only_ordered_ids(
    mocker,
    view_class,
    cache_path,
    id_field,
    timeout,
):
    object_id = uuid.uuid4()
    filtered_queryset = MagicMock()
    filtered_queryset.values_list.return_value = [object_id]
    view = view_class()
    view.get_queryset = mocker.Mock()
    view.filter_queryset = mocker.Mock(return_value=filtered_queryset)
    view._paginator = SimpleNamespace(
        page=SimpleNamespace(number=1),
    )
    view.paginate_queryset = mocker.Mock(return_value=[])
    view.get_paginated_response = mocker.Mock(return_value=Response([]))
    cache = mocker.patch(cache_path)
    cache.get.return_value = None

    view.list(_request('page=1&limit=20'))

    filtered_queryset.values_list.assert_called_once_with(id_field, flat=True)
    cache.set.assert_called_once()
    _, cached_value = cache.set.call_args.args[:2]
    assert cached_value == [str(object_id)]
    assert cache.set.call_args.kwargs['timeout'] == timeout


@pytest.mark.parametrize(
    ('view_class', 'cache_path', '_id_field', '_timeout'),
    LIST_CASES,
)
def test_list_cache_hit_skips_filter_query(
    mocker,
    view_class,
    cache_path,
    _id_field,
    _timeout,
):
    view = view_class()
    view.get_queryset = mocker.Mock()
    view.filter_queryset = mocker.Mock()
    view._paginator = SimpleNamespace(
        page=SimpleNamespace(number=2),
    )
    view.paginate_queryset = mocker.Mock(return_value=[])
    view.get_paginated_response = mocker.Mock(return_value=Response([]))
    cache = mocker.patch(cache_path)
    cache.get.return_value = [str(uuid.uuid4())]

    view.list(_request('page=2&limit=20'))

    view.filter_queryset.assert_not_called()
    cache.set.assert_not_called()


class _RetrieveBase:
    lookup_field = 'object_id'

    def retrieve(self, request, *args, **kwargs):
        return Response({'viewer': str(request.user.pk)})


class _CachedRetrieveView(CacheRetrieveMixin, _RetrieveBase):
    retrieve_cache_key_prefix = 'objects'
    retrieve_cache_timeout = 321


def test_retrieve_cache_is_per_viewer_and_uses_configured_ttl(mocker):
    cache = mocker.patch('core.cache_mixins.cache')
    cache.get.return_value = None
    object_id = uuid.uuid4()
    first_request = _request()
    second_request = _request()
    view = _CachedRetrieveView()

    view.retrieve(first_request, object_id=object_id)
    view.retrieve(second_request, object_id=object_id)

    first_key = f'objects:detail:{object_id}:{first_request.user.pk}'
    second_key = f'objects:detail:{object_id}:{second_request.user.pk}'
    assert first_key != second_key
    assert cache.get.call_args_list[0].args == (first_key,)
    assert cache.get.call_args_list[1].args == (second_key,)
    assert cache.set.call_args_list[0].kwargs['timeout'] == 321


def test_retrieve_cache_hit_does_not_call_serializer_path(mocker):
    cache = mocker.patch('core.cache_mixins.cache')
    cache.get.return_value = {'source': 'redis'}
    base_retrieve = mocker.patch.object(
        _RetrieveBase,
        'retrieve',
        return_value=Response({'source': 'database'}),
    )

    response = _CachedRetrieveView().retrieve(
        _request(),
        object_id=uuid.uuid4(),
    )

    assert response.data == {'source': 'redis'}
    base_retrieve.assert_not_called()
    cache.set.assert_not_called()


def test_counter_is_seeded_from_database_only_on_cache_miss(mocker):
    cache = mocker.patch('core.cache_mixins.cache')
    queryset = MagicMock()
    queryset.aggregate.return_value = {'c': 4}
    cache.get.side_effect = [None, 4]

    first = get_or_seed_counter('counter:test', '42', queryset)
    second = get_or_seed_counter('counter:test', '42', queryset)

    assert (first, second) == (4, 4)
    queryset.aggregate.assert_called_once()
    cache.set.assert_called_once_with('counter:test:42', 4)
