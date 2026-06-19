from django.urls import path

from feedback.views import FeedbackFileUploadView

app_name = 'feedback'

urlpatterns = [
    path(
        'files/upload/',
        FeedbackFileUploadView.as_view(),
        name='file-upload',
    ),
]