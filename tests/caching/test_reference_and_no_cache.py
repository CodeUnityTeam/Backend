# ruff: noqa

from django.core.cache import cache
from rest_framework.test import APIRequestFactory, force_authenticate

from core.cache_mixins import CacheRetrieveMixin
from core.constants.cache import TAGS_CACHE_TIMEOUT
from feedback.views import ReviewViewSet
from help.views import TagsListAPIView
from users.models import Skill
from users.views.profile import MeProfileView


def test_reference_endpoint_reuses_shared_json_and_ttl(mocker):
    Skill.objects.create(name='Django cache testing')
    request = APIRequestFactory().get('/tags/skills/')
    view = TagsListAPIView.as_view()
    set_spy = mocker.spy(cache, 'set')

    first_response = view(request, tag_type='skills')
    first_response.render()

    assert first_response.status_code == 200
    set_spy.assert_called_once()
    assert set_spy.call_args.args[0] == 'skills:list'
    assert set_spy.call_args.kwargs['timeout'] == TAGS_CACHE_TIMEOUT

    cached_payload = first_response.data
    Skill.objects.filter(name='Django cache testing').update(
        name='Changed without model signals',
    )
    second_response = view(request, tag_type='skills')

    assert second_response.data == cached_payload


def test_me_profile_is_http_no_cache_and_does_not_use_redis(
    mocker,
    verified_user,
):
    request = APIRequestFactory().get('/profile/me/')
    force_authenticate(request, user=verified_user)
    cache_get = mocker.spy(cache, 'get')
    cache_set = mocker.spy(cache, 'set')

    response = MeProfileView.as_view()(request)
    response.render()

    assert response.status_code == 200
    assert 'no-cache' in response['Cache-Control']
    assert 'no-store' in response['Cache-Control']
    cache_get.assert_not_called()
    cache_set.assert_not_called()


def test_reviews_remain_outside_redis_cache(mocker):
    request = APIRequestFactory().get('/reviews/')
    cache_get = mocker.spy(cache, 'get')
    cache_set = mocker.spy(cache, 'set')

    response = ReviewViewSet.as_view({'get': 'list'})(request)
    response.render()

    assert response.status_code == 200
    assert not issubclass(ReviewViewSet, CacheRetrieveMixin)
    cache_get.assert_not_called()
    cache_set.assert_not_called()
