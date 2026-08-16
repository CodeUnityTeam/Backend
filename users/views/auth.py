import logging
from typing import Any, cast

from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from users.serializers.auth import EmailChangeSerializer

UserModel = get_user_model()

logger = logging.getLogger(__name__)


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
                    'detail': (
                        'Ссылка для подтверждения отправлена на новый email.'
                    ),
                },
                response_only=True,
            ),
        ],
    ),
)
class EmailChangeView(APIView):
    """View для инициации смены email авторизованным пользователем."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, *_args: Any, **_kwargs: Any) -> Response:
        """Обработать POST-запрос на изменение email пользователя."""
        user = cast(User, request.user)
        logger.info(
            'Запрос на изменение email пользователя. user_id=%s, old_email=%s',
            user.user_id,
            user.email,
        )
        serializer = EmailChangeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        new_email: str = serializer.validated_data['new_email']
        serializer.save()

        logger.info(
            'Отправлено письмо подтверждения на новый email. '
            'user_id=%s, old_email=%s, new_email=%s',
            user.user_id,
            user.email,
            new_email,
        )

        return Response(
            {
                'detail': 'Ссылка подтверждения отправлена на новый email.',
            },
            status=status.HTTP_200_OK,
        )
