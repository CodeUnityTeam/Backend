import os
from typing import Any, Optional

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailConfirmation
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Model
from django.http import HttpRequest
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

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
        return os.getenv('HOST_URL', 'http://localhost:3000')

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


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер для контроля реактивации пользователя через провайдера."""

    def pre_social_login(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> None:
        """Проверить наличие зарегистрированного через провайдера пользователя.

        Если аккаунт был мягко удален, реактивируем его.
        """
        if sociallogin.is_existing:
            user = sociallogin.user

            if not user.is_active:
                # 1. Реактивируем пользователя
                user.is_active = True
                user.save(update_fields=['is_active'])

                # 2. Принудительно подтверждаем email
                email_address = user.emailaddress_set.filter(
                    email__iexact=user.email,
                ).first()
                if email_address and not email_address.verified:
                    email_address.verified = True
                    email_address.save(update_fields=['verified'])

                # 3. Форматируем название провайдера
                provider_id = sociallogin.account.provider
                provider_names = {
                    'yandex': 'Yandex',
                    'google': 'Google',
                    'mailru': 'Mail.ru',
                }
                provider_name = provider_names.get(
                    provider_id, provider_id.capitalize(),
                )

                # 4. Прерываем стандартный вход
                raise ImmediateResponseException(
                    detail={
                        'detail': (
                            'Ваш аккаунт был успешно восстановлен через '
                            f'{provider_name}. Пожалуйста, повторите вход.'
                        ),
                    },
                    status_code=status.HTTP_201_CREATED,
                )
