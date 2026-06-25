from django.urls import include, path
from rest_framework.routers import DefaultRouter

from feedback.views import FeedbackViewSet


app_name = 'feedback'

router = DefaultRouter()
router.register('', FeedbackViewSet, basename='feedback')

urlpatterns = [
    path('', include(router.urls)),
]
