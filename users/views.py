from typing import Any

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.mailru.views import MailRuOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.settings import SOCIALACCOUNT_PROVIDERS
from users.models.users import User
from users.serializers import (
    CustomUserDetailsSerializer,
    EmailChangeSerializer,
    PublicUserProfileSerializer,
    SocialAuthCodeRequestSerializer,
)

UserModel = get_user_model()


class SocialLogin(SocialLoginView):
    """Базовый View для обработки запросов авторизации.

    Обрабатывает запросы авторизации через сторонние приложения.
    """

    client_class = OAuth2Client


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Google',
        request=SocialAuthCodeRequestSerializer,
    ),
)
class GoogleLogin(SocialLogin):
    """View для обработки запросов авторизации через Google."""

    adapter_class = GoogleOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['google']['CALLBACK_URL']


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Yandex',
        request=SocialAuthCodeRequestSerializer,
    ),
)
class YandexLogin(SocialLogin):
    """View для обработки запросов авторизации через Yandex."""

    adapter_class = YandexOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['yandex']['CALLBACK_URL']


@extend_schema_view(
    post=extend_schema(
        tags=['social_auth'],
        summary='Вход через Mail.ru',
        request=SocialAuthCodeRequestSerializer,
    ),
)
class MailRuLogin(SocialLogin):
    """View для обработки запросов авторизации через Mail.ru."""

    adapter_class = MailRuOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS['mailru']['CALLBACK_URL']


@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля авторизованного пользователя',
        responses={200: CustomUserDetailsSerializer},
    ),
    patch=extend_schema(
        tags=['profile'],
        summary='Частично обновить данные авторизованного пользователя',
        request=CustomUserDetailsSerializer,
        responses={200: CustomUserDetailsSerializer},
    ),
)
class MeProfileView(RetrieveUpdateAPIView):
    """View просмотра и редактирования профиля авторизованного пользователя."""

    http_method_names = ['get', 'patch', 'head', 'options']
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Возвращает объект текущего авторизованного пользователя."""
        return self.request.user


@extend_schema_view(
    post=extend_schema(
        tags=['profile'],
        summary='Запрос на изменение email авторизованным пользователем',
        description='Запрос на смену email и отправку письма подтверждения.',
        request=EmailChangeSerializer,
        responses={
            200: inline_serializer(
                name='EmailChangeSuccessResponse',
                fields={
                    'detail': serializers.CharField(
                        help_text=(
                            'Сообщение об успешной отправке ссылки '
                            'подтверждения.'
                        ),
                    ),
                },
            ),
        },
        examples=[
            OpenApiExample(
                name='Успешный запрос',
                value={
                    "detail": (
                        "Ссылка для подтверждения отправлена на новый email."
                    ),
                },
                response_only=True,
            ),
        ],
    ),
)
class EmailChangeView(APIView):
    """View для инициации смены email авторизованным пользователем."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Обработать POST-запрос на изменение email пользователя."""
        serializer = EmailChangeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'detail': 'Ссылка подтверждения отправлена на новый email.',
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля неавторизованного пользователя',
        description='Данные доступны по ID пользователя.',
        responses={200: PublicUserProfileSerializer},
    ),
)
class UserProfileView(RetrieveAPIView):
    """View для просмотра профиля неавторизованного пользователяпо ID."""

    queryset = UserModel.objects.all()
    serializer_class = PublicUserProfileSerializer
    permission_classes = [IsAuthenticated]
