from django.urls import include, path
from rest_framework.routers import DefaultRouter

from qna.views import (
    AnswerViewSet,
    FileUploadView,
    QuestionViewSet,
    SkillViewSet,
)

app_name = 'qna'

router = DefaultRouter()
router.register('questions', QuestionViewSet, basename='questions')
router.register('answers', AnswerViewSet, basename='answers')
router.register('tags', SkillViewSet, basename='tags')

urlpatterns = [
    path('', include(router.urls)),
    path('files/upload/', FileUploadView.as_view(), name='file-upload'),
]
