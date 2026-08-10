import logging
import os
from typing import Any

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from allauth.account.utils import user_pk_to_url_str
from dj_rest_auth.registration.serializers import (
    RegisterSerializer,
    SocialLoginSerializer,
)
from dj_rest_auth.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
)
from django.contrib.sites.models import Site
from django.http import HttpRequest
from requests.exceptions import RequestException
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.constants.users import MSG_RESENT
from core.tasks import send_async_template_email
from users.adapters import ImmediateResponseException
from users.models import User
from users.validators import (
    validate_password_requirements,
    validate_user_name,
)

logger = logging.getLogger(__name__)


class SocialAuthUrlResponseSerializer(serializers.Serializer):
    """Сериализатор для возврата URL авторизации."""

    authorization_url = serializers.URLField(
        help_text='Url перенаправления пользователя на сторону провайдера.',
    )


class SafeSocialLoginSerializer(SocialLoginSerializer):
    """Сериализатор для безопасного входа через соцсети.

    Устраняет RelatedObjectDoesNotExist при автоматическом
    связывании аккаунтов по Email и обрабатывает сетевые сбои.
    """

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверяет данные кода и связывает пользователя."""
        try:
            # Запускаем оригинальную валидацию dj-rest-auth
            attrs = super().validate(attrs)
        except AttributeError as exc:
            # Ловим ошибку связи базы данных
            if type(exc).__name__ == 'RelatedObjectDoesNotExist':
                request = self._get_request()
                user: User | None = getattr(request, 'user', None)

                if user and not user.is_anonymous:
                    attrs['user'] = user
                    return attrs
            raise exc
        except RequestException as exc:
            # Перехватываем любые сетевые тайм-ауты сторонних соцсетей
            # и превращаем их в чистую ошибку 400 DRF
            raise ValidationError(
                {
                    'non_field_errors': [
                        'Внешний сервис авторизации временно недоступен. '
                        'Пожалуйста, попробуйте позже.',
                    ],
                },
            ) from exc
        except Exception as exc:
            raise exc

        return attrs


class CustomLoginSerializer(LoginSerializer):
    """Сериализатор для запроса на вход в сервис."""

    username = None
    email = serializers.EmailField(required=True)


class CustomRegisterSerializer(RegisterSerializer):
    """Сериализатор для базовой регистрации пользователя с одним паролем."""

    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(
        required=True,
        max_length=150,
        validators=[validate_user_name],
    )
    last_name = serializers.CharField(
        required=True,
        max_length=150,
        validators=[validate_user_name],
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password_requirements],
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Переопределить инициализатор класса, убрав ненужные поля."""
        super().__init__(*args, **kwargs)
        fields_to_pop = [
            'username',
            'password_confirm',
            'password1',
            'password2',
        ]
        for field in fields_to_pop:
            if field in self.fields:
                self.fields.pop(field)

    def validate_email(self, email: str) -> str:
        """Чистая валидация email на уникальность среди активных."""
        email = get_adapter().clean_email(email)
        user = User.objects.filter(email__iexact=email).first()
        if user and user.is_active:
            email_address = EmailAddress.objects.filter(
                user=user,
                email__iexact=email,
            ).first()
            if email_address and email_address.verified:
                raise serializers.ValidationError(
                    'Пользователь с таким email уже зарегистрирован.',
                )
        return email

    def validate(self, data: dict) -> dict:
        """Валидировать пароль на соответствие требований надежности."""
        password: str = data['password']
        get_adapter().clean_password(password, user=None)
        return data

    def get_cleaned_data(self) -> dict:
        """Переопределить поля стандартной настройки dj-rest-auth."""
        return {
            'email': self.validated_data.get('email'),
            'password1': self.validated_data.get('password'),
            'first_name': self.validated_data.get('first_name'),
            'last_name': self.validated_data.get('last_name'),
        }

    def custom_signup(self, request: HttpRequest, user: Any) -> None:
        """Сохранить поля в модель пользователя при регистрации."""
        user.first_name = self.validated_data.get('first_name')
        user.last_name = self.validated_data.get('last_name')
        user.save()

    def save(self, request: HttpRequest) -> Any:
        """Управление реактивацией мягко удаленных учетных записей."""
        email = self.validated_data.get('email')
        user = User.objects.filter(email__iexact=email).first()
        if user:
            email_address = EmailAddress.objects.filter(
                user=user,
                email__iexact=email,
            ).first()

            if not user.is_active:
                user.is_active = True
                user.save(update_fields=('is_active',))
                if email_address:
                    email_address.send_confirmation(request, signup=True)

                logger.info(
                    'Аккаунт %s ре активирован. Письмо отправлено.',
                    email,
                )
                raise ImmediateResponseException(
                    detail={'detail': MSG_RESENT},
                )

            if email_address and not email_address.verified:
                email_address.send_confirmation(request, signup=True)

                logger.info(
                    'Повторный запрос подтверждения для %s.',
                    email,
                )
                raise ImmediateResponseException(
                    detail={'detail': MSG_RESENT},
                )

        return super().save(request)


class EmailChangeSerializer(serializers.Serializer):
    """Сериализатор для запроса на смену email с сохранением в модель."""

    new_email = serializers.EmailField(required=True)

    def validate_new_email(self, value: str) -> str:
        """Валидация нового адреса электронной почты."""
        user = self.context['request'].user
        value = get_adapter().clean_email(value)

        if value == user.email:
            raise ValidationError('Этот email уже привязан к вашему аккаунту.')

        # Проверка уникальности по всей базе пользователей
        if User.objects.filter(email=value).exists():
            raise ValidationError('Пользователь с таким email уже существует.')

        # Проверка уникальности среди подтвержденных адресов в django-allauth
        if EmailAddress.objects.filter(email=value, verified=True).exists():
            raise ValidationError(
                'Этот email уже занят другим подтвержденным аккаунтом.',
            )

        return value

    def save(self, **kwargs: dict) -> User:
        """Сохранить new_email и отправить письма на старый и новый адреса."""
        user = self.context['request'].user
        request = self.context.get('request')
        new_email = self.validated_data['new_email']
        old_email = user.email

        # 1. Запоминаем новый email во временное поле модели
        user.new_email = new_email
        user.save(update_fields=('new_email',))

        # 2. Очищаем старые неподтвержденные попытки смены email
        EmailAddress.objects.filter(user=user, verified=False).delete()

        # 3. Создаем новую запись для подтверждения
        email_address = EmailAddress.objects.create(
            user=user,
            email=new_email,
            primary=False,
            verified=False,
        )

        # 4. Отправляем ссылку-подтверждение на НОВЫЙ email
        # (Использует шаблон email_confirmation_message)
        email_address.send_confirmation(request, signup=False)

        # 5. Отправляем уведомление на СТАРЫЙ email пользователя
        # (Использует ваши шаблоны email_changed_message.html/.txt)
        current_site = Site.objects.get_current()
        context = {
            'user': user,
            'from_email': old_email,
            'to_email': new_email,
            'current_site': current_site,
        }

        send_async_template_email.delay(
            to_email=old_email,
            subject=f'Изменение email на сайте {current_site.name}',
            template_base_name='account/email/email_changed_message',
            context=context,
        )

        return user


# noinspection HttpUrlsUsage
class CustomPasswordResetSerializer(PasswordResetSerializer):
    """Кастомный сериализатор для сброса пароля."""

    def get_email_options(self) -> dict[str, Any]:
        """Переопределить генератор ссылок для исключения NoReverseMatch."""
        options = super().get_email_options()

        def custom_url_generator(
            _request: Any, user: Any, temp_key: str,
        ) -> str:
            """Формирует прямую ссылку на фронтенд с uid и token."""
            host_url = os.getenv(
                'HOST_URL', 'http://localhost:3000',
            ).rstrip('/')
            if not host_url.startswith(('http://', 'https://')):
                host_url = f'http://{host_url}'
            uid = user_pk_to_url_str(user)

            return f'{host_url}/password-reset/confirm/{uid}/{temp_key}'

        options['url_generator'] = custom_url_generator
        return options


# noinspection DuplicatedCode
class CustomPasswordChangeSerializer(PasswordChangeSerializer):
    """Сериализатор смены текущего пароля через личный кабинет (одно поле)."""

    new_password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        validators=[validate_password_requirements],
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Удалить дефолтные поля подтверждения из OpenAPI схемы."""
        super().__init__(*args, **kwargs)
        self.fields.pop('new_password1', None)
        self.fields.pop('new_password2', None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Унифицированная валидация надежности и подмена полей для форм."""
        new_password: str = attrs['new_password']

        # Чистая валидация надежности без привязки к контексту пользователя
        get_adapter().clean_password(new_password, user=None)

        # Переопределяем поля для корректной инициализации SetPasswordForm
        attrs['new_password1'] = new_password
        attrs['new_password2'] = new_password

        return super().validate(attrs)


# noinspection DuplicatedCode
class CustomPasswordResetConfirmSerializer(PasswordResetConfirmSerializer):
    """Сериализатор сброса забытого пароля по ссылке из email (одно поле)."""

    new_password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        validators=[validate_password_requirements],
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Удалить дефолтные поля подтверждения из OpenAPI схемы."""
        super().__init__(*args, **kwargs)
        self.fields.pop('new_password1', None)
        self.fields.pop('new_password2', None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Унифицированная валидация надежности и подмена полей для форм."""
        new_password: str = attrs['new_password']

        # Чистая валидация надежности без привязки к контексту пользователя
        get_adapter().clean_password(new_password, user=None)

        # Переопределяем поля для корректной инициализации SetPasswordForm
        attrs['new_password1'] = new_password
        attrs['new_password2'] = new_password

        return super().validate(attrs)
