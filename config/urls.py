from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

v1_urlpatterns = [
    path('help/', include(('help.urls', 'help'), namespace='help')),
    path('user/', include(('users.urls', 'users'), namespace='users')),
    path('qna/', include(('qna.urls', 'qna'), namespace='qna')),
    path(
        'projects/',
        include(('projects.urls', 'projects'), namespace='projects'),
    ),
    path('feedback/',
         include(('feedback.urls', 'feedback'), namespace='feedbacks'),
    ),
    path(
        'schema/',
        SpectacularAPIView.as_view(),
        name='schema',
    ),
    path(
        'docs/swagger/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'docs/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(v1_urlpatterns)),
]
