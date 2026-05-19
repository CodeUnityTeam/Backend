from typing import Any

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer, UserDetailsSerializer
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.http import HttpRequest
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

UserModel = get_user_model()


class CustomLoginSerializer(LoginSerializer):
    """Сериализатор для запроса на вход в сревис."""

    username = None
    email = serializers.EmailField(required=True)


class SocialAuthCodeRequestSerializer(serializers.Serializer):
    """Сериализатор для авторизации через OAuth2."""

    code = serializers.CharField(
        required=True,
        help_text=(
            'Код авторизации (Authorization Code), полученный от '
            'OAuth-провайдера на фронтенде.'
        ),
    )


class CustomRegisterSerializer(RegisterSerializer):
    """Сериализатор для базовой регистрации пользователя."""

    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Переопределить инициализатор класса, убрав не нужные поля."""
        super().__init__(*args, **kwargs)

        fields_to_pop = [
            'username', 'password_confirm', 'password1', 'password2',
        ]
        for field in fields_to_pop:
            if field in self.fields:
                self.fields.pop(field)

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

    def custom_signup(self, request: HttpRequest, user: Model) -> None:
        """Сохранить поля в модель пользователя."""
        user.first_name = self.validated_data.get('first_name')
        user.last_name = self.validated_data.get('last_name')
        user.save()


class CustomUserDetailsSerializer(UserDetailsSerializer):
    """Сериализатор для отображения и изменения данных пользователя."""

    new_email = serializers.EmailField(write_only=True, required=False)

    class Meta(UserDetailsSerializer.Meta):
        """Конфигурация сериализируемых полей пользователя."""

        model = UserModel
        fields = ('pk', 'email', 'first_name', 'last_name', 'new_email')
        read_only_fields = ('pk', 'email')

    def validate_new_email(self, value: str) -> str:
        """Валидировать новый адрес электронной почты пользователя."""
        user = self.context['request'].user
        if value == user.email:
            raise ValidationError('Этот email уже привязан к вашему аккаунту.')

        # Проверить уникальность по всей базе пользователей
        if UserModel.objects.filter(email=value).exists():
            raise ValidationError('Пользователь с таким email уже существует.')

        # Проверить уникальность среди ожидающих подтверждения адресов
        if EmailAddress.objects.filter(email=value, verified=True).exists():
            raise ValidationError(
                'Этот email уже занят другим подтвержденным аккаунтом.',
            )

        return value

    def update(self, instance: Model, validated_data: dict) -> Model:
        """Обновить данные пользователя."""
        new_email = validated_data.pop('new_email', None)
        instance = super().update(instance, validated_data)

        if new_email:
            request = self.context.get('request')
            EmailAddress.objects.filter(user=instance, verified=False).delete()

            email_address = EmailAddress.objects.create(
                user=instance,
                email=new_email,
                primary=False,
                verified=False,
            )

            email_address.send_confirmation(request, signup=False)

        return instance
