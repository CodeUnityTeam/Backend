from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ProjectResponseViewSet,
    ProjectViewSet,
    ResponseFeedViewSet,
    ResponseStatusViewSet,
)

project_router = DefaultRouter()
project_router.register(
    r'responses',
    ResponseFeedViewSet,
    basename='responses',
)
project_router.register(r'', ProjectViewSet, basename='project')


urlpatterns = [
    path('', include(project_router.urls)),
    path(
        '<uuid:project_id>/responses/',
        ProjectResponseViewSet.as_view({'post': 'create'}),
        name='project-responses-create',
    ),
    path(
        '<uuid:project_id>/invite/<uuid:user_id>/',
        ProjectResponseViewSet.as_view({'post': 'invite'}),
        name='project-invite',
    ),
    path(
        'responses/<uuid:response_id>/status/',
        ResponseStatusViewSet.as_view({'patch': 'update'}),
        name='response-status-update',
    ),
]
