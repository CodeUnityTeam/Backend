from datetime import date
from typing import Any, Dict, Type

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from dj_rest_auth.serializers import UserDetailsSerializer
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
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
from users.models.users import User, UserExperience
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
        # TODO [USERS-10/15]: read_only_fields = ('id',) — неверное имя поля.
        #   В модели UserExperience (users/models/users.py:214) поле называется exp_id,
        #   а не id. Скорее всего, это не работает.
        #   Решение: read_only_fields = ('pk',) или ('exp_id',).
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
        # TODO [USERS-11/15]: Убедиться, что фронтенд понимает, почему email read-only.
        #   Поле email помечено как read-only, но пользователь может захотеть
        #   его изменить (для этого есть отдельный EmailChangeView).
        #   Это корректно, но стоит убедиться, что фронтенд знает о
        #   необходимости использовать отдельный эндпоинт для смены email.
        read_only_fields = ('pk', 'email', 'role', 'experiences')

    # TODO [USERS-12/15]: Заменить ручное управление M2M через _set_m2m_relations()
    #   на стандартный writable Nested Serializer DRF.
    #   Проблема: _set_m2m_relations (строка 126) вручную:
    #     1. Делает N+1 запросов: model_class.objects.get(pk=obj_id) в цикле.
    #     2. Удаляет все старые связи через .delete() без блокировки — гонка данных.
    #     3. Игнорирует DoesNotExist через continue — тихая потеря данных.
    #     4. Не использует стандартный DRF-механизм для вложенных M2M.
    #
    #   Решение через стандартный DRF:
    #   Использовать PrimaryKeyRelatedField + переопределить update() через
    #   validated_data с прямой передачей ID, а DRF сам сделает set().
    #
    #   ВАРИАНТ 1 — через SlugRelatedField (если нужно передавать ID):
    #   class CustomUserDetailsSerializer(UserDetailsSerializer):
    #       skills = serializers.SlugRelatedField(
    #           slug_field='skill_id',
    #           queryset=Skill.objects.all(),
    #           many=True,
    #           required=False,
    #       )
    #       specializations = serializers.SlugRelatedField(
    #           slug_field='spec_id',
    #           queryset=Specialization.objects.all(),
    #           many=True,
    #           required=False,
    #       )
    #       workformats = serializers.SlugRelatedField(
    #           slug_field='format_id',
    #           queryset=WorkFormat.objects.all(),
    #           many=True,
    #           required=False,
    #       )
    #
    #       def update(self, instance, validated_data):
    #           # DRF сам вызовет .set() для M2M полей, если они есть в validated_data
    #           skills = validated_data.pop('skills', None)
    #           specializations = validated_data.pop('specializations', None)
    #           workformats = validated_data.pop('workformats', None)
    #
    #           instance = super().update(instance, validated_data)
    #
    #           if skills is not None:
    #               instance.skills.set(skills)
    #           if specializations is not None:
    #               instance.specializations.set(specializations)
    #           if workformats is not None:
    #               instance.workformats.set(workformats)
    #
    #           return instance
    #
    #   ВАРИАНТ 2 — через PrimaryKeyRelatedField (если фронтенд шлёт UUID):
    #   skills = serializers.PrimaryKeyRelatedField(
    #       queryset=Skill.objects.all(),
    #       many=True,
    #       required=False,
    #       pk_field=serializers.UUIDField(),
    #   )
    #
    #   Преимущества:
    #     - DRF сам валидирует существование объектов (возвращает 400 при ошибке).
    #     - DRF сам делает bulk-запрос (один SELECT вместо N+1).
    #     - .set() делает атомарную замену через SQL (удаляет старые, добавляет новые).
    #     - Нет гонки данных — .set() выполняется в рамках одной транзакции.
    #     - Убирается _set_m2m_relations целиком.
    #
    #   Важно: через-модели (UserSkill, UserSpecialization, UserWorkFormat)
    #   должны иметь корректные Meta.unique_together, чтобы .set() работал.
    #   Если в through-модели есть дополнительные поля — нужно использовать
    #   through_defaults или inline-сериализаторы.
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


# TODO [USERS-13/15]: Удалить дубликат EmailChangeSerializer.
#   Этот же сериализатор определён в users/serializers/auth.py:139.
#   Нужно импортировать его оттуда, а этот класс удалить.
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
