from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
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
        if (
            project.author == user and
            project.author.projects_relation ==
            User.ProjectsRelationChoices.EMPLOYER
        ):
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
        return [
            {'skill_id': str(s.skill_id), 'name': s.name}
            for s in instance.project.skills.all()
        ]

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
