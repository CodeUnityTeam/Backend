from typing import Any, Type

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from dj_rest_auth.serializers import UserDetailsSerializer
from django.contrib.auth import get_user_model
from django.db import models, transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from config import settings
from core.validators import file_size_validator
from projects.models import WorkFormat
from projects.serializers import (
    SkillSerializer,
    SpecializationSerializer,
    WorkFormatSerializer,
)
from users.models.skills import Skill, UserSkill
from users.models.specializations import Specialization, UserSpecialization
from users.models.users import User
from users.models.workformats import UserWorkFormat

UserModel = get_user_model()


class CustomUserDetailsSerializer(UserDetailsSerializer):
    """Сериализатор для отображения и изменения данных пользователя."""

    workformats = WorkFormatSerializer(required=False, many=True)
    skills = SkillSerializer(required=False, many=True)
    specializations = SpecializationSerializer(required=False, many=True)

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
            'skills',
            'specializations',
            'workformats',
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
        format_data = validated_data.pop('workformats', None)
        skill_data = validated_data.pop('skills', None)
        spec_data = validated_data.pop('specializations', None)

        instance = super().update(instance, validated_data)

        with transaction.atomic():
            if format_data is not None:
                self._set_m2m_relations(
                    instance=instance,
                    data=format_data,
                    model_class=WorkFormat,
                    through_model_class=UserWorkFormat,
                    fk_field_name='workformat',
                )
            if skill_data is not None:
                self._set_m2m_relations(
                    instance=instance,
                    data=skill_data,
                    model_class=Skill,
                    through_model_class=UserSkill,
                    fk_field_name='skill',
                )
            if spec_data is not None:
                self._set_m2m_relations(
                    instance=instance,
                    data=spec_data,
                    model_class=Specialization,
                    through_model_class=UserSpecialization,
                    fk_field_name='specialization',
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


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для публичного просмотра чужого профиля."""

    skills = SkillSerializer(many=True, read_only=True)
    specializations = SpecializationSerializer(many=True, read_only=True)
    workformats = WorkFormatSerializer(many=True, read_only=True)

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
            'skills',
            'specializations',
            'workformats',
            'avatar_url',
        )

        read_only_fields = fields


class AvatarUploadSerializer(serializers.Serializer[dict[str, Any]]):
    """Сериализатор для валидации загружаемого файла аватара."""

    file: serializers.ImageField = serializers.ImageField(
        validators=[file_size_validator(
            max_size_mb=settings.ALLOW_AVATAR_SIZE_MB,
        )],
        write_only=True,
    )
