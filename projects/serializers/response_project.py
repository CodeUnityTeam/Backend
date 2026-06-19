from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.constants.projects import (
    APPLICANT,
    APPROVED,
    AUTHOR,
    MEMBER,
    PENDING,
    PUBLISHED,
    REJECTED,
    STATUS_RESPONSE_PROJECT,
    WITHDRAWN,
)
from projects.models import Project, ProjectParticipant, Response
from projects.serializers import ProjectShortSerializer
from projects.services import (
    add_user_to_project_participants,
    create_response,
)

User = get_user_model()


class ResponseUserProjectSerializer(serializers.ModelSerializer):
    """Сериализатор для создания отклика на проект."""

    class Meta:
        model = Response
        fields = [
            'response_id',
            'project',
            'user',
            'initiator_type',
            'status_resp',
        ]
        read_only_fields = [
            'response_id',
            'project',
            'user',
            'initiator_type',
            'status_resp',
        ]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием отклика."""
        project = self.context['project']
        user = self.context['request'].user
        if project.author == user:
            raise serializers.ValidationError(
                'Нельзя откликнуться на собственный проект.',
            )
        if project.status_project != PUBLISHED:
            raise serializers.ValidationError(
                f'Отклик возможен только на проекты со статусом {PUBLISHED}.',
            )
        if Response.objects.filter(project=project, user=user).exists():
            raise serializers.ValidationError(
                'Вы уже откликнулись на этот проект.',
            )
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Response:
        """Создание отклика."""
        project = self.context['project']
        user = self.context['request'].user
        return create_response(project, user)


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
    """Сериализатор для инвайта в проект."""

    class Meta:
        model = Response
        fields = [
            'project',
            'user',
        ]
        read_only_fields = [
            'project',
            'user',
        ]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием инвайта."""
        project_id = self.context['project_id']
        user_id = self.context['user_id']
        project = get_object_or_404(Project, project_id=project_id)
        user = get_object_or_404(User, user_id=user_id)
        if project.author == user:
            raise serializers.ValidationError(
                'Нельзя пригласить самого автора проекта',
            )
        if Response.objects.filter(project=project, user=user).exists():
            raise serializers.ValidationError('Приглашение уже существует')
        attrs['project'] = project
        attrs['user'] = user
        attrs['initiator_type'] = AUTHOR
        attrs['status_resp'] = PENDING
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Project:
        """Создание инвайта на проект (автором проекта)."""
        return create_response(
            project=validated_data['project'],
            user=validated_data['user'],
            initiator_type=validated_data['initiator_type'],
            status_resp=validated_data['status_resp'],
        )


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
        if user_response.status_resp != PENDING:
            raise serializers.ValidationError(
                f'Статус можно изменить только из pending, '
                f'текущий статус: {user_response.status_resp}',
            )
        return status

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед изменением статуса."""
        user_response = self.instance
        request = self.context['request']
        user = request.user
        new_status = attrs['status']
        permissions = {
            APPROVED: [
                (
                    user_response.initiator_type == AUTHOR and
                    user_response.user == user
                ),  # пользователь принимает приглашение
                (
                    user_response.initiator_type == APPLICANT and
                    user_response.project.author == user
                ),  # автор одобряет отклик
            ],
            REJECTED: [
                (
                    user_response.initiator_type == AUTHOR and
                    user_response.user == user
                ),  # пользователь отклоняет приглашение
                (
                    user_response.initiator_type == APPLICANT and
                    user_response.project.author == user
                ),  # автор отклоняет отклик
            ],
            WITHDRAWN: [
                (
                    user_response.initiator_type == APPLICANT and
                    user_response.user == user
                ),  # пользователь отзывает отклик
                (
                    user_response.initiator_type == AUTHOR and
                    user_response.project.author == user
                ),  # автор отменяет приглашение
            ],
        }
        if not any(permissions.get(new_status, [])):
            error_messages = {
                APPROVED: 'Нет прав для одобрения этого отклика/приглашения',
                REJECTED: 'Нет прав для отклонения этого отклика/приглашения',
                WITHDRAWN: 'Инициатор может отозвать свой отклик/приглашение',
            }
            raise serializers.ValidationError(error_messages[new_status])
        if new_status == APPROVED and ProjectParticipant.objects.filter(
            project=user_response.project,
            user=user_response.user,
        ).exists():
            raise serializers.ValidationError(
                'Пользователь уже является участником проекта',
            )
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


class ProjectCardConditionalSerializer(ProjectShortSerializer):
    """Сериализатор проекта с условным добавлением контактов автора.

    Используется при фильтрации ленты откликов/приглашений.
    """

    author_email = serializers.EmailField(
        source='author.email',
        read_only=True,
        required=False,
        allow_null=True,
    )
    author_phone = serializers.CharField(
        source='author.phone_number',
        read_only=True,
        required=False,
        allow_null=True,
    )

    class Meta(ProjectShortSerializer.Meta):
        fields = ProjectShortSerializer.Meta.fields + [
            'author_email',
            'author_phone',
        ]

    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """Форматируем поля для ответа."""
        data = super().to_representation(instance)
        response = self.context.get('response')
        user = self.context.get('user')
        # Добавляем контакты автора только если:
        # response_status == 'approved'
        # текущий пользователь — участник проекта (соискатель)
        if not (
            response and response.status_resp == APPROVED and
            user and user.id == response.user_id
        ):
            data.pop('author_email', None)
            data.pop('author_phone', None)
        return data


class FeedbackAndInvitationFeedSerializer(serializers.Serializer):
    """Сериализатор для ленты откликов с условными полями.

    Для выдачи информации использует ProjectCardConditionalSerializer.
    Пользователь получает проекты где он откликнулся.
    """

    response_id = serializers.UUIDField()
    response_status = serializers.CharField(source='status_resp')
    response_created_at = serializers.DateTimeField(source='created_at')
    project = serializers.SerializerMethodField()

    def get_project(
        self,
        instance: Response,
    ) -> None | Optional[Dict[str, Any]]:
        """Получаем проекты где пользователь откликнулся."""
        if self.get_card_type(instance) == 'project' and instance.project:
            serializer = ProjectCardConditionalSerializer(
                instance.project,
                context={
                    'user': self.context.get('user'),
                    'response': instance,
                    'request': self.context.get('request'),
                },
            )
            return serializer.data
        return None

    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """Форматируем поля для ответа."""
        data = super().to_representation(instance)
        card_type = data['card_type']
        result = {
            'response_id': data['response_id'],
            'response_status': data['response_status'],
            'response_created_at': data['response_created_at'],
        }
        return result
