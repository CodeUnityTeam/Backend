import logging
from typing import Any, Dict

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.cache_mixins import get_or_seed_counter
from core.constants.cache import COUNTER_PROJECT_PARTICIPANTS_PREFIX
from core.constants.projects import (
    APPLICANT,
    APPROVED,
    AUTHOR,
    MEMBER,
    PENDING,
    STATUS_RESPONSE_PROJECT,
)
from projects.models import Response
from projects.models.project import ProjectParticipant
from projects.serializers.skill import SkillSerializer
from projects.services import add_user_to_project_participants
from projects.validators.response_project import (
    validate_can_change_status,
    validate_can_create_response,
    validate_can_invite,
)

logger = logging.getLogger(__name__)


class ResponseUserProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для создания отклика на проект (только для worker)."""

    class Meta:
        model = Response
        fields = (
            'response_id', 'project', 'user', 'initiator_type', 'status_resp',
        )
        read_only_fields = fields

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием отклика."""
        project = self.context['project']
        user = self.context['request'].user
        validate_can_create_response(project, user)
        return {
            'project': project,
            'user': user,
            'initiator_type': APPLICANT,
            'status_resp': PENDING,
        }


class ResponseResponseCreateProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для формирования ответа после создания отклика."""

    response_id = serializers.UUIDField(read_only=True)
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
        fields = (
            'response_id',
            'project_id',
            'user_id',
            'status',
            'created_at',
        )


class InviteUserProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для приглашения пользователя в проект.

    Проект уже получен во вьюхе и передан в контекст.
    """

    class Meta:
        model = Response
        fields = (
            'response_id', 'project', 'user', 'initiator_type', 'status_resp',
        )
        read_only_fields = fields

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием инвайта."""
        project = self.context['project']
        user_id = self.context['user_id']
        request = self.context['request']
        user = validate_can_invite(project, request.user, user_id)
        return {
            'project': project,
            'user': user,
            'initiator_type': AUTHOR,
            'status_resp': PENDING,
        }


class UpdateResponseStatusSerializer(serializers.ModelSerializer):
    """Сериализатор для изменения статуса отклика/приглашения."""

    status = serializers.ChoiceField(
        choices=STATUS_RESPONSE_PROJECT,
        help_text='Новый статус отклика',
    )

    class Meta:
        model = Response
        fields = ('status',)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация прав на изменение статуса."""
        if 'status' not in attrs:
            raise serializers.ValidationError({
                'status': 'Это поле обязательно для заполнения.',
            })
        if self.instance is None:
            raise serializers.ValidationError(
                'Изменение статуса возможно только для существующего отклика.',
            )
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
        user_response.save(update_fields=('status_resp',))
        if new_status == APPROVED:
            add_user_to_project_participants(
                project=user_response.project,
                user=user_response.user,
                status=MEMBER,
            )
        return user_response


class UpdateResponseStatusResponseSerializer(serializers.ModelSerializer):
    """Сериализатор для ответа после изменения статуса отклика."""

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
        fields = ('response_id', 'project_id', 'user_id', 'status')


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
    participants_count = serializers.SerializerMethodField()
    is_liked_by_me = serializers.BooleanField(
        read_only=True,
    )
    # Контакты автора (только для approved)
    author_email = serializers.SerializerMethodField()
    author_phone = serializers.SerializerMethodField()

    def get_participants_count(self, instance: Response) -> int:
        """Количество участников из Redis-счётчика (с fallback на БД)."""
        count = get_or_seed_counter(
            COUNTER_PROJECT_PARTICIPANTS_PREFIX,
            str(instance.project_id),
            ProjectParticipant.objects.filter(project=instance.project),
        )
        logger.debug(
            'participants_count для отклика %s (проект %s): %d',
            instance.response_id, instance.project_id, count,
        )
        return count

    @extend_schema_field(SkillSerializer(many=True))
    def get_skills(self, instance: Response) -> list[dict]:
        """Навыки проекта из prefetch_related (без доп. запроса)."""
        if not instance.project_id:
            return []
        return SkillSerializer(
            instance.project.skills.all(),
            many=True,
        ).data

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
