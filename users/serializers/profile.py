from datetime import date
from typing import Any, Dict, Type

from dj_rest_auth.serializers import UserDetailsSerializer
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from rest_framework import serializers

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
from users.models.users import UserExperience
from users.models.workformats import UserWorkFormat

UserModel = get_user_model()


class UserExperienceSerializer(
    serializers.ModelSerializer[UserExperience],
):
    """Сериализатор для модели опыта работы пользователя."""

    class Meta:
        model = UserExperience
        fields = (
            'pk',
            'company',
            'position',
            'responsibilities',
            'start_date',
            'end_date',
        )
        read_only_fields = ('id',)

    def validate_start_date(self, value: date) -> date:
        """Проверка, что дата начала работы не в будущем."""
        current_date: date = timezone.now().date()
        if value > current_date:
            raise serializers.ValidationError(
                'Дата начала работы не может быть позже текущей даты.',
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Проверка хронологии дат начала и окончания работы."""
        start_date: date | None = attrs.get('start_date')
        end_date: date | None = attrs.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {
                    'end_date': (
                        'Дата окончания не может быть '
                        'раньше даты начала.'
                    ),
                },
            )
        return attrs


class CustomUserDetailsSerializer(UserDetailsSerializer):
    """Сериализатор для отображения и изменения данных пользователя."""

    experiences = UserExperienceSerializer(
        many=True,
        read_only=True,
    )
    skills = SkillSerializer(required=False, many=True)
    specializations = SpecializationSerializer(required=False, many=True)
    workformats = WorkFormatSerializer(required=False, many=True)

    class Meta(UserDetailsSerializer.Meta):
        """Конфигурация сериализируемых полей пользователя."""

        model = UserModel
        fields = (
            'pk',
            'email',
            'first_name',
            'last_name',
            'role',
            'projects_relation',
            'phone_number',
            'additional_contact',
            'country',
            'city',
            'soft_skills',
            'about_me',
            'avatar_url',
            'skills',
            'specializations',
            'workformats',
            'experiences',
        )
        read_only_fields = ('pk', 'email', 'role', 'experiences')

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


class AvatarUploadSerializer(serializers.Serializer[dict[str, Any]]):
    """Сериализатор для валидации загружаемого файла аватара."""

    file: serializers.ImageField = serializers.ImageField(
        validators=[file_size_validator(
            allow_size_mb=settings.ALLOW_AVATAR_SIZE_MB,
        )],
        write_only=True,
    )


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для списочного отображения профилей."""

    skills = SkillSerializer(many=True, read_only=True)
    specializations = SpecializationSerializer(
        many=True, read_only=True,
    )
    workformats = WorkFormatSerializer(many=True, read_only=True)

    class Meta:
        model = UserModel
        fields = (
            'pk',
            'first_name',
            'last_name',
            'city',
            'skills',
            'specializations',
            'workformats',
            'avatar_url',
        )
        read_only_fields = fields


class DetailUserProfileSerializer(PublicUserProfileSerializer):
    """Сериализатор для детального просмотра чужого профиля."""

    experiences = UserExperienceSerializer(
        many=True, read_only=True,
    )

    class Meta(PublicUserProfileSerializer.Meta):
        fields = PublicUserProfileSerializer.Meta.fields + (
            'country',
            'role',
            'soft_skills',
            'about_me',
            'experiences',
        )
        read_only_fields = fields
