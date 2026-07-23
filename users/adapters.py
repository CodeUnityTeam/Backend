import os
from typing import Any, Dict, Optional

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailConfirmation
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.mail import EmailMessage
from django.db.models import Model
from django.http import HttpRequest
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from users.utils import email_service

UserModel = get_user_model()


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
    """Адаптер для процесса регистрации и управления пользователем."""

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
        """Получить url ссылки на подтверждение email."""
        host_url = os.getenv('HOST_URL', 'http://localhost:3000')
        if not host_url.startswith(('http://', 'https://')):
            host_url = f'https://{host_url}'
        return f'{host_url}/register/verify-email/{emailconfirmation.key}'

    def respond_email_verification_sent(
        self,
        request: HttpRequest,
        user: Model,
    ) -> Response:
        """Сформировать ответ на запрос регистрации в сервисе."""
        return Response(
            {'detail': 'Письмо с подтверждением выслано.'},
            status=status.HTTP_201_CREATED,
        )

    def render_mail(
        self,
        template_prefix: str,
        email: str,
        context: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
    ) -> EmailMessage:
        """Перехватывает рендеринг писем для EmailService."""
        site_name = context['current_site'].name

        # 1. Подтверждение регистрации
        if 'email_confirmation' in template_prefix:
            context['code'] = None
            email_service.send_template_email(
                to_email=email,
                subject=f'Подтверждение регистрации: {site_name}',
                template_base_name=(
                    'account/email/email_confirmation_message'
                ),
                context=context,
            )
            return self._create_dummy_message()

        # 2. Восстановление пароля
        if 'password_reset_key' in template_prefix:
            email_service.send_template_email(
                to_email=email,
                subject=f'Восстановление пароля: {site_name}',
                template_base_name=(
                    'account/email/password_reset_key_message'
                ),
                context=context,
            )
            return self._create_dummy_message()

        return super().render_mail(
            template_prefix, email, context, headers,
        )

    def _create_dummy_message(self) -> EmailMessage:
        """Создает заглушку для блокировки дефолтной отправки."""

        class DummyMessage(EmailMessage):
            def send(self, fail_silently: bool = False) -> int:
                return 0

        return DummyMessage()


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
