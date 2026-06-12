from typing import Any, Optional

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailConfirmation
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Model
from django.http import HttpRequest
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from users.utils import get_frontend_url

UserModel = get_user_model()

MSG_SUCCESS = 'Письмо с подтверждением успешно отправлено на ваш email.'
MSG_RESENT = (
    'Письмо с подтверждением успешно отправлено на ваш email повторно.'
)


class ImmediateResponseException(APIException):
    """Кастомное исключение для мгновенного возврата HTTP-ответа."""

    status_code = status.HTTP_201_CREATED

    def __init__(
        self,
        detail: Optional[Any] = None,
        status_code: Optional[int] = None,
    ) -> None:
        """Добавить статус код экземпляру исключения."""
        if status_code:
            self.status_code = status_code
        super().__init__(detail=detail)


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
        """Получить url для формирования ссылки на подтверждение email."""
        return get_frontend_url('email', emailconfirmation.key)

    def respond_email_verification_sent(
        self,
        request: HttpRequest,
        user: Model,
    ) -> Response:
        """Сформировать ответ на запрос регистрации в сервисе."""
        return Response(
            {'detail': MSG_SUCCESS},
            status=status.HTTP_201_CREATED,
        )
