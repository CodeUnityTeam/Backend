from typing import Any, Dict

from rest_framework import serializers

from core.constants.projects import (
    APPLICANT,
    APPROVED,
    AUTHOR,
    MEMBER,
    PENDING,
    STATUS_RESPONSE_PROJECT,
)
from projects.models import Response
from projects.services import add_user_to_project_participants
from projects.validators.response_project import (
    validate_can_change_status,
    validate_can_create_response,
    validate_can_invite,
    validate_status_can_be_changed,
)


class ResponseUserProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для создания отклика на проект (только для worker)."""

    class Meta:
        model = Response
        fields = [
            'response_id',
            'project',
            'user',
            'initiator_type',
            'status_resp',
        ]
        read_only_fields = fields

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием отклика."""
        project = self.context['project']
        user = self.context['request'].user
        validate_can_create_response(project, user)
        attrs['project'] = project
        attrs['user'] = user
        attrs['initiator_type'] = APPLICANT
        attrs['status_resp'] = PENDING
        return attrs


class ResponseResponseCreateProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для формирования ответа после создания отклика."""

    project_id = serializers.UUIDField(
        source='project.project_id',
        read_only=True,
    )
    user_id = serializers.UUIDField(
        source='user.user_id',
        read_only=True,
    )
    status = serializers.CharField(
        source='status_resp',
        read_only=True,
    )

    class Meta:
        model = Response
        fields = ['project_id', 'user_id', 'status', 'created_at']


class InviteUserProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для приглашения пользователя в проект.

    Проект уже получен во вьюхе и передан в контекст.
    """

    class Meta:
        model = Response
        fields = [
            'response_id',
            'project',
            'user',
            'initiator_type',
            'status_resp',
        ]
        read_only_fields = fields

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием инвайта."""
        project = self.context['project']
        user_id = self.context['user_id']
        request = self.context['request']
        user = validate_can_invite(project, request.user, user_id)
        attrs['project'] = project
        attrs['user'] = user
        attrs['initiator_type'] = AUTHOR
        attrs['status_resp'] = PENDING
        return attrs


class UpdateResponseStatusSerializer(serializers.ModelSerializer):
    """Сериализатор для изменения статуса отклика/приглашения."""

    status = serializers.ChoiceField(
        choices=STATUS_RESPONSE_PROJECT,
        help_text='Новый статус отклика',
    )

    class Meta:
        model = Response
        fields = ['status']

    def validate_status(self, status: str) -> str:
        """Валидация нового статуса."""
        user_response = self.instance
        if not user_response:
            raise serializers.ValidationError('Отклик не найден')
        validate_status_can_be_changed(user_response)
        return status

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация прав на изменение статуса."""
        user_response = self.instance
        user = self.context['request'].user
        new_status = attrs['status']
        validate_can_change_status(user_response, user, new_status)
        return attrs

    def update(
        self,
        user_response: Response,
        validated_data: Dict[str, Any],
    ) -> Response:
        """Обновление статуса и сопутствующие действия."""
        new_status = validated_data['status']
        user_response.status_resp = new_status
        user_response.save()
        if new_status == APPROVED:
            add_user_to_project_participants(
                project=user_response.project,
                user=user_response.user,
                status=MEMBER,
            )
            user_response.project.save()
        return user_response


class FeedbackAndInvitationFeedSerializer(serializers.Serializer):
    """Сериализатор для ленты откликов/приглашений.

    Возвращает поля отклика и проекта на одном уровне.
    - Когда response_status == 'approved' — добавляются
      author_email и author_phone автора проекта.
    - Когда response_status == 'pending' — контакты автора скрыты.

    Все данные получает из аннотированного queryset
    (get_response_feed_queryset).
    """
    # Поля отклика
    response_id = serializers.UUIDField(read_only=True)
    response_status = serializers.CharField(
        source='status_resp',
        read_only=True,
    )
    response_created_at = serializers.DateTimeField(
        source='created_at',
        read_only=True,
    )
    # Поля проекта (на верхнем уровне, через source)
    project_id = serializers.UUIDField(
        source='project.project_id',
        read_only=True,
    )
    title = serializers.CharField(
        source='project.title',
        read_only=True,
    )
    short_desc = serializers.CharField(
        source='project.short_desc',
        read_only=True,
    )
    skills = serializers.SerializerMethodField()
    location = serializers.CharField(
        source='project.location',
        read_only=True,
        allow_null=True,
    )
    status = serializers.CharField(
        source='project.status_project',
        read_only=True,
    )
    published_at = serializers.DateTimeField(
        source='project.published_at',
        read_only=True,
        allow_null=True,
    )
    participants_count = serializers.IntegerField(
        read_only=True,
    )
    is_liked_by_me = serializers.BooleanField(
        read_only=True,
    )
    # Контакты автора (только для approved)
    author_email = serializers.SerializerMethodField()
    author_phone = serializers.SerializerMethodField()

    def get_skills(self, instance: Response) -> list[dict]:
        """Навыки проекта из prefetch_related (без доп. запроса)."""
        if not instance.project_id:
            return []
        return [skill.name for skill in instance.project.skills.all()]

    def get_author_email(self, instance: Response) -> str | None:
        """Email автора — только для approved откликов."""
        if instance.status_resp == APPROVED:
            return instance.project.author.email
        return None

    def get_author_phone(self, instance: Response) -> str | None:
        """Телефон автора — только для approved откликов."""
        if instance.status_resp == APPROVED:
            return instance.project.author.phone_number
        return None

    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """Форматируем поля для ответа.

        Удаляем author_email и author_phone, если они None
        (т.е. статус не approved).
        """
        data = super().to_representation(instance)
        if data.get('author_email') is None:
            data.pop('author_email', None)
        if data.get('author_phone') is None:
            data.pop('author_phone', None)
        return data
