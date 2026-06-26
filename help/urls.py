from django.urls import path
from drf_spectacular.utils import extend_schema

from help.views import TagsListAPIView

urlpatterns = (
    path(
        '<str:tag_type>/',
        extend_schema(tags=['Help'])(TagsListAPIView).as_view(),
        name='schema',
    ),
)
