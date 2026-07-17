from django.urls import path

from documents.views import DocumentsListView

app_name = 'documents'

urlpatterns = [
    path('', DocumentsListView.as_view(), name='documents-list'),
]
