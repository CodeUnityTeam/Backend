from typing import Any

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.http import HttpRequest
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.adapters import MSG_RESENT, ImmediateResponseException
from users.models.users import User
from users.utils import get_frontend_url

UserModel = get_user_model()


class SocialAuthUrlResponseSerializer(serializers.Serializer):
    """Сериализатор для возврата URL авторизации."""

    authorization_url = serializers.URLField(
        help_text="Url перенаправления пользователя на сторону провайдера.",
    )


class SocialAuthCodeRequestSerializer(serializers.Serializer):
    """Сериализатор для авторизации через OAuth2."""

    code = serializers.CharField(
        required=True,
        help_text=(
            'Код авторизации (Authorization Code), полученный от '
            'OAuth-провайдера на фронтенде.'
        ),
    )


class CustomLoginSerializer(LoginSerializer):
    """Сериализатор для запроса на вход в сревис."""

    username = None
    email = serializers.EmailField(required=True)


class CustomRegisterSerializer(RegisterSerializer):
    """Сериализатор для базовой регистрации пользователя с одним паролем."""

    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Переопределить инициализатор класса, убрав ненужные поля."""
        super().__init__(*args, **kwargs)

        fields_to_pop = [
            'username', 'password_confirm', 'password1', 'password2',
        ]
        for field in fields_to_pop:
            if field in self.fields:
                self.fields.pop(field)

    # TODO [USERS]: Убрать сайд-эффекты из validate_email().
    #   Метод не только проверяет email, но и:
    #   1. Реактивирует мягко удалённого пользователя (строки 87-88) — мутация БД.
    #   2. Отправляет письмо через ImmediateResponseException (строки 93-95).
    #   Это нарушает принцип разделения ответственности — валидатор не должен
    #   иметь сайд-эффектов.
    #   Решение: перенести логику реактивации и отправки письма в services.py
    #   или в CustomAccountAdapter (users/adapters.py).
    def validate_email(self, email: str) -> str:
        """Валидация email с обработкой удаленных аккаунтов."""
        email = get_adapter().clean_email(email)
        user = UserModel.objects.filter(email__iexact=email).first()

        if user:
            request = self.context.get('request')
            email_address = EmailAddress.objects.filter(
                user=user, email__iexact=email,
            ).first()

            # Пользователь мягко удален
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=['is_active'])

                if email_address:
                    email_address.send_confirmation(request, signup=True)

                raise ImmediateResponseException(
                    detail={"detail": MSG_RESENT},
                )

            # Пользователь активен, но email не подтвержден
            if email_address and not email_address.verified:
                email_address.send_confirmation(request, signup=True)
                raise ImmediateResponseException(
                    detail={"detail": MSG_RESENT},
                )

            # Активный подтвержденный пользователь
            raise serializers.ValidationError(
                "Пользователь с таким email уже зарегистрирован.",
            )

        return email

    # TODO [USERS]: Убрать создание объекта UserModel для валидации пароля.
    #   На строках 115-119 создаётся экземпляр UserModel(...) без сохранения в БД
    #   только для передачи в clean_password. validate_password из Django принимает
    #   user=None, поэтому объект не нужен.
    #   Решение: передавать user=None в get_adapter().clean_password().
    def validate(self, attrs: dict) -> dict:
        """Валидировать пароль на соответствие требований надежности."""
        password = attrs.get('password')

        user = UserModel(
            email=attrs.get('email'),
            first_name=attrs.get('first_name'),
            last_name=attrs.get('last_name'),
        )
        get_adapter().clean_password(password, user=user)
        return attrs

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
        if UserModel.objects.filter(email=value).exists():
            raise ValidationError('Пользователь с таким email уже существует.')

        # Проверка уникальности среди подтвержденных адресов в django-allauth
        if EmailAddress.objects.filter(email=value, verified=True).exists():
            raise ValidationError(
                'Этот email уже занят другим подтвержденным аккаунтом.',
            )

        return value

    def save(self) -> User:
        """Сохранить new_emailи отправить письмо для подтверждения."""
        user = self.context['request'].user
        request = self.context.get('request')
        new_email = self.validated_data['new_email']

        user.new_email = new_email
        user.save(update_fields=['new_email'])

        EmailAddress.objects.filter(user=user, verified=False).delete()

        email_address = EmailAddress.objects.create(
            user=user,
            email=new_email,
            primary=False,
            verified=False,
        )

        email_address.send_confirmation(request, signup=False)

        return user


# TODO [USERS]: Переименовать поле password в new_password.
#   Фронтенд отправляет password, внутри оно маппится в new_password1/new_password2
#   (строки 209-210). Это неочевидно и может запутать.
#   Решение: переименовать поле в new_password для ясности.
class CustomPasswordChangeSerializer(PasswordChangeSerializer):
    """Сериализатор для смены пароля с одним полем нового пароля."""

    password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Удалить стандартные поля подтверждения пароля из формы."""
        super().__init__(*args, **kwargs)
        self.fields.pop('new_password1', None)
        self.fields.pop('new_password2', None)

    def validate_password(self, value: str) -> str:
        """Проверить надежность нового пароля по стандартам Django."""
        user = self.context['request'].user
        validate_password(value, user=user)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Перераспределить данные для стандартных методов dj-rest-auth."""
        attrs['new_password1'] = attrs.get('password')
        attrs['new_password2'] = attrs.get('password')

        return super().validate(attrs)


class CustomPasswordResetSerializer(PasswordResetSerializer):
    """Кастомный сериализатор для сброса пароля."""

    def get_email_options(self) -> dict[str, any]:
        """Переопределяет генератор ссылок внутри опций формы."""
        options: dict[str, any] = super().get_email_options()

        def custom_url_generator(
            request: HttpRequest,
            user: User,
            temp_key: str,
        ) -> str:
            """Формирует прямую ссылку на фронтенд."""
            return get_frontend_url("password", temp_key)

        options["url_generator"] = custom_url_generator
        return options
