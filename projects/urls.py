from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet

project_router = DefaultRouter()
project_router.register(r'', ProjectViewSet, basename='project')


urlpatterns = [
    path('', include(project_router.urls)),
]
