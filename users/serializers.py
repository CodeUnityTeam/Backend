from typing import Any, Type

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    UserDetailsSerializer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import models, transaction
from django.db.models import Model
from django.http import HttpRequest
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.models.skills import Skill, UserSkill
from users.models.specializations import Specialization, UserSpecialization
from users.models.users import User

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


class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения и привязки навыков пользователя."""

    class Meta:
        model = Skill
        fields = ('skill_id', 'name')
        read_only_fields = ('name',)
        extra_kwargs = {
            'skill_id': {'read_only': False},
        }


class SpecializationSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения специализаций."""

    class Meta:
        model = Specialization
        fields = ('spec_id', 'name')
        read_only_fields = ('name',)
        extra_kwargs = {
            'spec_id': {'read_only': False},
        }


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

    specializations = SpecializationSerializer(required=False, many=True)
    skills = SkillSerializer(required=False, many=True)

    class Meta(UserDetailsSerializer.Meta):
        """Конфигурация сериализируемых полей пользователя."""

        model = UserModel
        fields = (
            'pk',
            'email',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'additional_contact',
            'country',
            'city',
            'about_me',
            'specializations',
            'skills',
            'avatar_url',
        )
        read_only_fields = ('pk', 'email', 'role')

    def _set_m2m_relations(
        self,
        instance: Any,
        data: list[dict[str, Any]],
        model_class: Type[models.Model],
        through_model_class: Type[models.Model],
        fk_field_name: str,
    ) -> None:
        """Универсальный метод для добавления M2M связей."""
        pk_field_name = model_class._meta.pk.name

        objects_to_add = []
        for item in data:
            obj_id = item.get(pk_field_name)
            if not obj_id:
                continue
            try:
                obj = model_class.objects.get(pk=obj_id)
                if obj not in objects_to_add:
                    objects_to_add.append(obj)
            except model_class.DoesNotExist:
                continue

        # Удаляем старые связи
        through_model_class.objects.filter(user=instance).delete()

        # Формируем новые связи
        new_relations = [
            through_model_class(**{'user': instance, fk_field_name: obj})
            for obj in objects_to_add
        ]
        through_model_class.objects.bulk_create(new_relations)

    def update(self, instance: Any, validated_data: dict[str, Any]) -> Any:
        """Обновить профиль, специализации и навыки пользователя."""
        spec_data = validated_data.pop('specializations', None)
        skill_data = validated_data.pop('skills', None)

        instance = super().update(instance, validated_data)

        with transaction.atomic():
            if spec_data is not None:
                self._set_m2m_relations(
                    instance=instance,
                    data=spec_data,
                    model_class=Specialization,
                    through_model_class=UserSpecialization,
                    fk_field_name='specialization',
                )
            if skill_data is not None:
                self._set_m2m_relations(
                    instance=instance,
                    data=skill_data,
                    model_class=Skill,
                    through_model_class=UserSkill,
                    fk_field_name='skill',
                )

        instance.save()
        return instance


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


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для публичного просмотра чужого профиля."""

    specializations = SpecializationSerializer(required=False, many=True)
    skills = SkillSerializer(required=False, many=True)

    class Meta:
        model = UserModel
        fields = (
            'pk',
            'first_name',
            'last_name',
            'role',
            'country',
            'city',
            'about_me',
            'specializations',
            'skills',
            'avatar_url',
        )

        read_only_fields = fields
