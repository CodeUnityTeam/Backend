from django.urls import include, path

from users.views.auth import (
    EmailChangeView,
    GoogleAuthUrlView,
    GoogleLogin,
    MailRuAuthUrlView,
    MailRuLogin,
    YandexAuthUrlView,
    YandexLogin,
)
from users.views.profile import (
    MeProfileView,
    UserAvatarAPIView,
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

            # Эндпоинты для получения ссылок авторизации (GET)
            path(
                'google/url/',
                GoogleAuthUrlView.as_view(),
                name='google_auth_url',
            ),
            path(
                'yandex/url/',
                YandexAuthUrlView.as_view(),
                name='yandex_auth_url',
            ),
            path(
                'mailru/url/',
                MailRuAuthUrlView.as_view(),
                name='mailru_auth_url',
            ),

            # dj-rest-auth для социальных сетей (POST для обмена code на JWT)
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
                "me/avatar/",
                UserAvatarAPIView.as_view(),
                name="user-avatar",
            ),
            path(
                'email-change/',
                EmailChangeView.as_view(),
                name='email-change',
            ),
            path('<uuid:pk>/', UserProfileView.as_view(), name='user-profile'),
        ]),
    ),
]
