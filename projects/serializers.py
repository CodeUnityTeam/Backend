from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.constants.projects import ALLOWED_STATUSED_FOR_LIKE, PUBLISHED
from users.serializers import SkillSerializer, SpecializationSerializer

from .models import Project, ProjectLike, Response, WorkFormat
from .selectors import get_project_or_404
from .validators import (
    add_relationships_to_project,
    extract_relationship_data,
)

User = get_user_model()


class WorkFormatSerializer(serializers.ModelSerializer):
    """Сериализатор форматов работы."""

    class Meta:
        model = WorkFormat
        fields = ('format_id', 'name')


class UserBaseSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя — для обычных пользователей в проекте."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('user_id', 'full_name', 'avatar_url')

    def get_full_name(self, user: User) -> str:
        """Получаем полное имя пользователя."""
        return f'{user.first_name} {user.last_name}'.strip()


class UserAuthorShortSerializer(UserBaseSerializer):
    """Краткий сериализатор для автора — дополняется последней активностью."""

    last_activity_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserBaseSerializer.Meta.fields + ('last_activity_at',)

    def get_last_activity_at(self, user: User) -> str:
        """Метод для выдачи последней активности пользователя."""
        if user.last_login:
            return user.last_login.isoformat()
        return None


class UserAuthorSerializer(UserAuthorShortSerializer):
    """Сериализатор для автора проекта — дополнительные поля."""

    class Meta:
        model = User
        fields = UserAuthorShortSerializer.Meta.fields + ('email', 'phone')


class UserParticipantSerializer(UserAuthorSerializer):
    """Сериализатор для участника проекта — те же поля, что у автора."""

    pass


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания проекта."""

    skills = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='Список навыков в формате [{"skill_id": "uuid"}]',
    )
    specializations = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='Список специализаций в формате [{"spec_id": "uuid"}]',
    )
    project_format = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text='Список форматов работы в формате ["uuid", "uuid"]',
    )

    class Meta:
        model = Project
        fields = [
            'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status_project', 'skills', 'specializations', 'project_format',
        ]

    def validate(self, data: dict) -> dict:
        """Дополнительная валидация дат начала и окончания проекта."""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                'end_date': 'Дата начала не может быть позже даты окончания',
            })
        return data

    @transaction.atomic
    def create(self, validated_data: dict) -> Project:
        """Метод для валидации и создания проекта."""
        relationship_data = extract_relationship_data(validated_data)
        user = self.context['request'].user
        validated_data['author'] = user
        if validated_data.get('status_project') == 'published':
            validated_data['published_at'] = timezone.now()
        project = Project.objects.create(**validated_data)
        add_relationships_to_project(project, relationship_data)
        return project


class ProjectCreationResponseSerializer(serializers.ModelSerializer):
    """Сериализатор для ответа на создание проекта."""

    status = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ('project_id', 'status', 'created_at', 'published_at')

    def get_status(self, project: Project) -> str:
        """Меняем название поля для выдачи информации."""
        return project.status_project


class ProjectShortSerializer(serializers.ModelSerializer):
    """Сериализатор для краткой информации о проекте (для списка проектов)."""

    skills = SkillSerializer(many=True, read_only=True)
    is_liked_by_me = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'project_id', 'title', 'short_desc', 'location',
            'status_project', 'published_at', 'participants_count',
            'is_liked_by_me', 'skills',
        ]

    def get_is_liked_by_me(self, project: Project) -> bool:
        """Проверяем, лайкнул ли проект авторизированный пользователь."""
        user = self.context.get('request').user
        if not user.is_authenticated:
            return False
        return ProjectLike.objects.filter(
            user=user,
            project=project,
        ).exists()

    def get_participants_count(self, project: Project) -> int:
        """Получаем количество участников проекта."""
        return project.participants.count()


class ProjectDetailSerializer(ProjectShortSerializer):
    """Сериализатор детальной карточки проекта."""

    specializations = SpecializationSerializer(many=True, read_only=True)
    project_format = WorkFormatSerializer(many=True, read_only=True)
    likes_count = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    full_desc = serializers.SerializerMethodField()

    class Meta(ProjectShortSerializer.Meta):
        fields = ProjectShortSerializer.Meta.fields + [
            'full_desc', 'end_date', 'specializations',
            'project_format', 'likes_count', 'participants', 'author',
        ]

    def get_likes_count(self, project: Project) -> int:
        """Получаем лайки проекта."""
        return project.likes.count()

    def get_participants(self, project: Project) -> list:
        """Получаем инфу об участниках проекта.

        Информация отображается в зависимости от роли пользователя в проекте:
        - Обычный и участник видят только ID, full_name, аватар участников.
        - Автор видит ID, full_name, аватар, email, phone участников.
        """
        requesting_user = self.context.get('request').user
        is_author = project.author == requesting_user
        if is_author:
            participant_serializer = UserParticipantSerializer
        else:
            participant_serializer = UserBaseSerializer
        return participant_serializer(
            project.participants.all(),
            many=True,
        ).data

    def get_author(self, project: Project) -> list:
        """Метод для показа информации о авторе проекта.

        - Участник проекта может видеть всю информацию об авторе.
        - Обычный пользователь и автор видят краткую инфу об авторе.
        """
        requesting_user = self.context.get('request').user
        is_participant = requesting_user in project.participants.all()
        if is_participant:
            author_serializer = UserAuthorSerializer
        else:
            author_serializer = UserAuthorShortSerializer
        return author_serializer(project.author).data

    def get_full_desc(self, project: Project) -> str | None:
        """Условное поле: показывается только для автора и участников."""
        requesting_user = self.context.get('request').user
        if (requesting_user in project.participants.all()):
            return project.full_desc
        return None


class ProjectArchiveSerializer(serializers.Serializer):
    """Сериализатор для архивирования проекта."""

    def save(self, **kwargs: dict) -> Project:
        """Архивирует проект: переводит в статус 'archived'."""
        project = self.instance
        project.status_project = 'archived'
        project.save(update_fields=['status_project'])
        return project


class ProjectLikeResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа после создани/удаления лайка."""

    liked = serializers.BooleanField()
    likes_count = serializers.IntegerField()


class ProjectLikeSerializer(serializers.Serializer):
    """Сериализатор для лайков."""

    def validate_project_id(self, project_id: str) -> str:
        """Используем готовую функцию для получения проекта или 404."""
        project = get_project_or_404(str(project_id))
        if project.status_project not in ALLOWED_STATUSED_FOR_LIKE:
            raise serializers.ValidationError(
                'Нельзя лайкать проект с текущим статусом.',
            )
        self.context['project'] = project
        return project_id

    def toggle_like(self) -> dict:
        """Toggle-логика: создание/удаление лайка."""
        user = self.context['request'].user
        project = self.context['project']
        like_exists = ProjectLike.objects.filter(
            user=user,
            project=project,
        ).exists()
        if like_exists:
            ProjectLike.objects.filter(user=user, project=project).delete()
            liked = False
        else:
            ProjectLike.objects.create(user=user, project=project)
            liked = True
        return {
            'liked': liked,
            'likes_count': ProjectLike.objects.filter(project=project).count(),
        }


class ProjectUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления проекта."""

    skills = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    specializations = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    formats = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Project
        fields = [
            'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status', 'skills', 'specializations', 'formats',
        ]
        extra_kwargs = {
            'title': {'required': False},
            'short_desc': {'required': False},
            'full_desc': {'required': False},
            'location': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False},
            'status': {'required': False, 'source': 'status_project'},
        }

    def validate_status(self, status_project: str) -> str:
        """Валидация статуса проекта."""
        if status_project is None:
            return status_project
        valid_statuses = ['draft', 'published', 'recruiting_closed']
        if status_project not in valid_statuses:
            raise serializers.ValidationError(
                f'Статус должен быть одним из: {", ".join(valid_statuses)}.',
            )
        return status_project

    @transaction.atomic
    def update(self, project: Project, validated_data: dict) -> Project:
        """Метод для обновления проекта."""
        relationship_data = extract_relationship_data(validated_data)
        for attr, value in validated_data.items():
            if hasattr(project, attr):
                setattr(project, attr, value)
        project.save()
        add_relationships_to_project(project, relationship_data)
        return Project.objects.select_related(
            'author',
        ).prefetch_related(
            'skills',
            'specializations',
            'project_format',
        ).get(project_id=project.project_id)


class ProjectUpdateResponseSerializer(serializers.ModelSerializer):
    """Сериализатор для формирования ответа после обновления проекта."""

    status = serializers.CharField(source='status_project', read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    specializations = SpecializationSerializer(many=True, read_only=True)
    formats = WorkFormatSerializer(
        many=True,
        read_only=True,
        source='project_format',
    )

    class Meta:
        model = Project
        fields = [
            'project_id', 'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status', 'published_at', 'created_at',
            'skills', 'specializations', 'formats',
        ]


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
        return Response.objects.create(
            project=project,
            user=user,
            initiator_type='applicant',
            status_resp='pending',
        )


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
