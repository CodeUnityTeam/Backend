from django.urls import include, path

from users.views.auth import (
    EmailChangeView,
    GoogleLogin,
    MailRuLogin,
    YandexLogin,
)
from users.views.profile import (
    MeProfileView,
    UserProfileListView,
    UserProfileView,
)

urlpatterns = [
    path(
        'auth/',
        include([
            # dj-rest-auth для базовой авторизации
            path('', include('dj_rest_auth.urls')),
            path('registration/', include('dj_rest_auth.registration.urls')),
            # dj-rest-auth для социальных сетей
            path('google/', GoogleLogin.as_view(), name='google_login'),
            path('yandex/', YandexLogin.as_view(), name='yandex_login'),
            path('mailru/', MailRuLogin.as_view(), name='mailru_login'),
        ]),
    ),

    path(
        'profile/',
        include([
            path('', UserProfileListView.as_view(), name='profile-list'),
            path('me/', MeProfileView.as_view(), name='my-profile'),
            path(
                'email-change/',
                EmailChangeView.as_view(),
                name='email-change',
            ),
            path('<uuid:pk>/', UserProfileView.as_view(), name='user-profile'),
        ]),
    ),
]
