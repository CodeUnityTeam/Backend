from dj_rest_auth.registration.views import (
    RegisterView,
    ResendEmailVerificationView,
    VerifyEmailView,
)
from dj_rest_auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

from core.throttling import (
    LoginRateThrottle,
    PasswordChangeRateThrottle,
    PasswordResetRateThrottle,
    RegisterRateThrottle,
)
from users.views.auth import (
    EmailChangeView,
    GoogleAuthUrlView,
    GoogleLogin,
    MailRuAuthUrlView,
    MailRuLogin,
    YandexAuthUrlView,
    # YandexCallbackView,
    YandexLogin,
)
from users.views.profile import (
    MeExperienceViewSet,
    MeProfileView,
    ProfileLikeAPIView,
    UserAvatarAPIView,
    UserProfileListView,
    UserProfileView,
)

router = SimpleRouter()
router.register(
    r'',
    MeExperienceViewSet,
    basename='my-experience',
)

CHANGE_DESCRIPTION = (
    'Изменяет текущий пароль авторизованного пользователя.\n'
    'Требует ввод старого пароля и одного нового пароля.'
)

LOGIN_DESCRIPTION = (
    'Аутентификация пользователя по email и паролю.\n'
    'Устанавливает сессионные куки и возвращает JWT-токены.'
)

LOGOUT_DESCRIPTION = (
    'Выход пользователя из системы.\n'
    'Инвалидирует текущий токен и очищает авторизационные куки.'
)

REFRESH_DESCRIPTION = (
    'Обновление пары JWT-токенов (access и refresh).\n'
    'Принимает действующий refresh-токен и выдает новый access-токен.'
)

REGISTER_DESCRIPTION = (
    'Регистрирует нового пользователя в системе.\n'
    'Создает учетную запись и отправляет письмо для подтверждения email.'
)

RESEND_EMAIL_DESCRIPTION = (
    'Повторно отправляет письмо с ключом подтверждения на email.\n'
    'Используется, если предыдущее письмо не дошло или истек '
    'срок действия ключа.'
)

RESET_CONFIRM_DESCRIPTION = (
    'Принимает токен, UID из письма и устанавливает новый пароль.\n'
    'Требует ввод одного нового пароля без подтверждения.'
)

RESET_DESCRIPTION = (
    'Отправляет на email ссылку для восстановления пароля.\n'
    'Формат ссылки: {HOST_URL}/password-reset/confirm/{uid}/{token}'
)

VERIFY_DESCRIPTION = (
    'Проверка валидности текущего JWT-токена.\n'
    'Позволяет фронтенду быстро убедиться, что access-токен еще не истек.'
)

VERIFY_EMAIL_DESCRIPTION = (
    'Подтверждает email пользователя по ключу из ссылки в письме.\n'
    'Активирует учетную запись для возможности авторизации.'
)

urlpatterns = (
    path(
        'auth/',
        include([
            path(
                'login/',
                extend_schema(
                    tags=['auth'],
                    summary='Вход в систему (Авторизация)',
                    description=LOGIN_DESCRIPTION,
                )(LoginView).as_view(
                    throttle_classes=[LoginRateThrottle],
                ),
                name='rest_login',
            ),
            path(
                'logout/',
                extend_schema(
                    tags=['auth'],
                    summary='Выход из системы',
                    description=LOGOUT_DESCRIPTION,
                )(LogoutView).as_view(),
                name='rest_logout',
            ),
            path(
                'token/refresh/',
                extend_schema(
                    tags=['auth'],
                    summary='Обновление JWT-токена',
                    description=REFRESH_DESCRIPTION,
                )(TokenRefreshView).as_view(),
                name='token_refresh',
            ),
            path(
                'token/verify/',
                extend_schema(
                    tags=['auth'],
                    summary='Проверка валидности токена',
                    description=VERIFY_DESCRIPTION,
                )(TokenVerifyView).as_view(),
                name='token_verify',
            ),
            path(
                'password/change/',
                extend_schema(
                    tags=['auth'],
                    summary='Смена пароля',
                    description=CHANGE_DESCRIPTION,
                )(PasswordChangeView).as_view(
                    throttle_classes=[PasswordChangeRateThrottle],
                ),
                name='rest_password_change',
            ),
            path(
                'password/reset/',
                extend_schema(
                    tags=['auth'],
                    summary='Запрос на сброс пароля',
                    description=RESET_DESCRIPTION,
                )(PasswordResetView).as_view(
                    throttle_classes=[PasswordResetRateThrottle],
                ),
                name='rest_password_reset',
            ),
            path(
                'password/reset/confirm/',
                extend_schema(
                    tags=['auth'],
                    summary='Подтверждение сброса пароля',
                    description=RESET_CONFIRM_DESCRIPTION,
                )(PasswordResetConfirmView).as_view(),
                name='rest_password_reset_confirm',
            ),
            path(
                'registration/',
                include([
                    path(
                        '',
                        extend_schema(
                            tags=['auth'],
                            summary='Регистрация нового пользователя',
                            description=REGISTER_DESCRIPTION,
                        )(RegisterView).as_view(
                            throttle_classes=[RegisterRateThrottle],
                        ),
                        name='rest_register',
                    ),
                    path(
                        'verify-email/',
                        extend_schema(
                            tags=['auth'],
                            summary='Подтверждение email',
                            description=VERIFY_EMAIL_DESCRIPTION,
                        )(VerifyEmailView).as_view(),
                        name='rest_verify_email',
                    ),
                    path(
                        'resend-email/',
                        extend_schema(
                            tags=['auth'],
                            summary='Повторная отправка подтверждения email',
                            description=RESEND_EMAIL_DESCRIPTION,
                        )(ResendEmailVerificationView).as_view(),
                        name='rest_resend_email',
                    ),
                ]),
            ),
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
            # path(
            #     'yandex/callback/',
            #     YandexCallbackView.as_view(),
            #     name='yandex_callback',
            # ),
            path(
                'mailru/url/',
                MailRuAuthUrlView.as_view(),
                name='mailru_auth_url',
            ),
            path(
                'google/callback',
                GoogleLogin.as_view(),
                name='google_login',
            ),
            path(
                'yandex/callback',
                YandexLogin.as_view(),
                name='yandex_login',
            ),
            path(
                'mailru/callback',
                MailRuLogin.as_view(),
                name='mailru_login',
            ),
        ]),
    ),
    path(
        'profile/',
        include([
            path(
                '',
                UserProfileListView.as_view(),
                name='profile-list',
            ),
            path(
                'email-change/',
                EmailChangeView.as_view(),
                name='email-change',
            ),
            path(
                '<uuid:pk>/',
                UserProfileView.as_view(),
                name='user-profile',
            ),
            path(
                '<uuid:worker_id>/like/',
                ProfileLikeAPIView.as_view(),
                name='profile-like',
            ),
            path(
                'me/',
                include([
                    path(
                        '',
                        MeProfileView.as_view(),
                        name='my-profile',
                    ),
                    path(
                        'avatar/',
                        UserAvatarAPIView.as_view(),
                        name='user-avatar',
                    ),
                    path(
                        'experience/',
                        include(router.urls),
                    ),
                ]),
            ),
        ]),
    ),
)
