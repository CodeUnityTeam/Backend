import os

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailConfirmation
from django.contrib.auth.password_validation import validate_password
from django.db.models import Model
from django.http import HttpRequest
from rest_framework import status
from rest_framework.response import Response


class CustomAccountAdapter(DefaultAccountAdapter):
    """Адаптер для процесса регистрации пользователя."""

    def clean_password(
        self,
        password: str,
        user: Model = None,
        password_sign_up: bool = True,
    ) -> str:
        """Валидировать пароль."""
        validate_password(password, user=user)
        return password

    def get_email_confirmation_url(
        self,
        request: HttpRequest,
        emailconfirmation: EmailConfirmation,
    ) -> str:
        """Получить url для формирования ссылки на подверждение email."""
        frontend_url = os.getenv('HOST_URL')
        return f"{frontend_url}/{emailconfirmation.key}"

    def respond_email_verification_sent(
        self,
        request: HttpRequest,
        user: Model,
    ) -> Response:
        """Сформировать ответ на запрос регистрации в сервисе."""
        return Response(
            {
                "detail": (
                    "Письмо с подтверждением успешно отправлено на ваш email."
                ),
            },
            status=status.HTTP_201_CREATED,
        )
