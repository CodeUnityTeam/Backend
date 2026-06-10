from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# TODO [SYSTEM-10/10]: static() для STATIC_URL не нужен.
#   static() предназначен для MEDIA_ROOT, а не STATIC_ROOT.
#   В dev статику раздаёт django.contrib.staticfiles, в production — nginx.
#   Эта строка может вызвать проблемы. Нужно удалить.
urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'api/v1/',
        include(
            [
                path(
                    'user/',
                    include(('users.urls', 'users'), namespace='users'),
                ),

                path('qna/', include(('qna.urls', 'qna'), namespace='qna')),
                path(
                    'projects/',
                    include(
                        ('projects.urls', 'projects'), namespace='projects',
                    ),
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
            ],
        ),
    ),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
