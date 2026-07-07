from datetime import date
from typing import Any, Dict

from dj_rest_auth.serializers import UserDetailsSerializer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from config import settings
from core.validators import file_size_validator
from projects.models import Response as ProjectResponse
from projects.models import WorkFormat
from projects.serializers import (
    SkillSerializer,
    SpecializationSerializer,
    WorkFormatSerializer,
)
from users.models.skills import Skill
from users.models.specializations import Specialization
from users.models.users import User, UserExperience, UserLike

UserModel = get_user_model()


class DRFErrorResponseSerializer(serializers.Serializer):
    """Стандартная структура ошибки Django REST Framework."""

    detail = serializers.CharField(
        help_text='Текстовое сообщение с деталями ошибки.',
    )


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
        read_only_fields = ('pk',)

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


class MeProfileUpdateSerializer(UserDetailsSerializer):
    """Сериализатор для изменения данных профиля (PATCH)."""

    skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        required=False,
    )
    specializations = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        many=True,
        required=False,
    )
    workformats = serializers.PrimaryKeyRelatedField(
        queryset=WorkFormat.objects.all(),
        many=True,
        required=False,
    )

    class Meta(UserDetailsSerializer.Meta):
        """Конфигурация сериализируемых полей пользователя."""

        model = UserModel
        fields = (
            'projects_relation',
            'first_name',
            'last_name',
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
        )

    def update(self, instance: Any, validated_data: dict) -> Any:
        """Обновить профиль, специализации и навыки пользователя."""
        skills = validated_data.pop('skills', None)
        specializations = validated_data.pop('specializations', None)
        workformats = validated_data.pop('workformats', None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if skills is not None:
                instance.skills.set(skills)
            if specializations is not None:
                instance.specializations.set(specializations)
            if workformats is not None:
                instance.workformats.set(workformats)

        return instance


class MeProfileRetrieveSerializer(MeProfileUpdateSerializer):
    """Сериализатор для просмотра данных профиля (GET)."""

    experiences = UserExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    specializations = SpecializationSerializer(many=True, read_only=True)
    workformats = WorkFormatSerializer(many=True, read_only=True)
    rating = serializers.IntegerField(read_only=True)

    class Meta(MeProfileUpdateSerializer.Meta):
        """Конфигурация полей профиля для чтения."""

        model = UserModel
        fields = (
            'pk',
            'email',
            'role',
            'experiences',
            'rating',
        ) + MeProfileUpdateSerializer.Meta.fields
        read_only_fields = fields


class AvatarUploadSerializer(serializers.Serializer[dict[str, Any]]):
    """Сериализатор для валидации загружаемого файла аватара."""

    file: serializers.ImageField = serializers.ImageField(
        validators=[file_size_validator(
            allow_size_mb=settings.S3_MAX_FILE_SIZE_MB,
        )],
        write_only=True,
    )


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для списочного отображения профилей."""

    is_liked = serializers.SerializerMethodField()
    skills = SkillSerializer(many=True, read_only=True)
    specializations = SpecializationSerializer(many=True, read_only=True)
    workformats = WorkFormatSerializer(many=True, read_only=True)
    rating = serializers.IntegerField(read_only=True)

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
            'is_liked',
            'rating',
        )
        read_only_fields = fields

    def get_is_liked(self, obj: User) -> bool:
        """Определяет, лайкнул ли текущий пользователь этот профиль."""
        request = self.context['request']
        employer: User = request.user

        if hasattr(obj, 'annotated_is_liked'):
            return obj.annotated_is_liked

        if (
            employer.projects_relation
            != UserModel.ProjectsRelationChoices.EMPLOYER
        ):
            return False

        return UserLike.objects.filter(
            employer=employer,
            worker=obj,
        ).exists()


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


class UserResponseCardSerializer(serializers.ModelSerializer):
    """Сериализатор карточки отклика с вложенным профилем соискателя."""

    response_id: serializers.UUIDField = serializers.UUIDField(
        read_only=True,
    )
    project_id: serializers.UUIDField = serializers.UUIDField(
        source='project.project_id', read_only=True,
    )
    project_title: serializers.CharField = serializers.CharField(
        source='project.title', read_only=True,
    )
    profile: PublicUserProfileSerializer = (
        PublicUserProfileSerializer(source='user', read_only=True)
    )

    class Meta:
        model = ProjectResponse
        fields = (
            'response_id',
            'project_id',
            'project_title',
            'initiator_type',
            'status_resp',
            'profile',
        )
        read_only_fields = fields


class UserLikeSerializer(serializers.ModelSerializer):
    """Сериализатор для валидации и создания лайков."""

    class Meta:
        model = UserLike
        fields = ('worker',)

    def validate(self, attrs: dict) -> dict:
        """Проверка бизнес-правил перед созданием лайка."""
        employer = self.context['request'].user
        worker = attrs.get('worker')

        # 1. Проверяем роль автора лайка
        if (
            employer.projects_relation
            != User.ProjectsRelationChoices.EMPLOYER
        ):
            raise ValidationError(
                'Чтобы поставить лайк, пользователь должен быть '
                'автором проекта.',
            )

        # 2. Проверяем активность лайкаемого пользователя
        if not worker.is_active:
            raise ValidationError(
                'Можно лайкать только активных пользователей.',
            )

        return attrs
