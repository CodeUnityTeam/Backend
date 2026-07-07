from django.urls import include, path
from rest_framework.routers import DefaultRouter

from feedback.views import FeedbackViewSet, ReviewViewSet

app_name = 'feedback'

reviews_router = DefaultRouter()
reviews_router.register('reviews', ReviewViewSet, basename='reviews')

feedback_router = DefaultRouter()
feedback_router.register('', FeedbackViewSet, basename='feedback')

urlpatterns = [
    path('', include(feedback_router.urls)),
]
