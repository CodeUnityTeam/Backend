from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/v1/",
        include(
            [
                path(
                    "auth/",
                    include(('users.urls', 'users'), namespace='users')
                ),
                path(
                    'schema/',
                    SpectacularAPIView.as_view(),
                    name='schema'
                ),
                # Swagger UI
                path(
                    'docs/swagger/',
                    SpectacularSwaggerView.as_view(url_name='schema'),
                    name='swagger-ui'
                ),
                # ReDoc
                path(
                    'docs/redoc/',
                    SpectacularRedocView.as_view(url_name='schema'),
                    name='redoc'
                ),
            ]
        ),
    ),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
