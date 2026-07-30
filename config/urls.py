from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from feedback.urls import reviews_router
from users.views.auth import (
    GoogleCallbackView,
    MailRuCallbackView,
    YandexCallbackView,
)

v1_urlpatterns = [
    path('help/', include(('help.urls', 'help'), namespace='help')),
    path('user/', include(('users.urls', 'users'), namespace='users')),
    path('qna/', include(('qna.urls', 'qna'), namespace='qna')),
    path(
        'projects/',
        include(('projects.urls', 'projects'), namespace='projects'),
    ),
    path(
        'feedback/',
        include(('feedback.urls', 'feedback'), namespace='feedbacks'),
    ),
    path('', include(reviews_router.urls)),
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
    path(
        'documents/',
        include(('documents.urls', 'documents'), namespace='documents'),
    ),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(v1_urlpatterns)),
    # OAuth callback endpoints — доступны по /auth/... через nginx
    path(
        'auth/yandex/callback/',
        YandexCallbackView.as_view(),
        name='yandex_callback',
    ),
    path(
        'auth/google/callback/',
        GoogleCallbackView.as_view(),
        name='google_callback',
    ),
    path(
        'auth/mailru/callback/',
        MailRuCallbackView.as_view(),
        name='mailru_callback',
    ),
]
