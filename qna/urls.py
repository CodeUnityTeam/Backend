from django.urls import include, path
from rest_framework.routers import DefaultRouter

from qna.views.answer import AnswerViewSet
from qna.views.question import QuestionViewSet
from qna.views.skill import SkillViewSet
from qna.views.file import FileUploadView


app_name = 'qna'

router = DefaultRouter()
router.register('questions', QuestionViewSet, basename='questions')
router.register('answers', AnswerViewSet, basename='answers')
router.register('tags', SkillViewSet, basename='tags')

urlpatterns = [
    path('', include(router.urls)),
    path('files/upload/', FileUploadView.as_view(), name='file-upload'),
]
