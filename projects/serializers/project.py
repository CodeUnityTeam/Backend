from django.utils import timezone

from django.db import transaction
from rest_framework import serializers

from projects.models import Project, ProjectLike
from projects.selectors import get_project_with_relations
from projects.validators import (
    add_relationships_to_project,
    extract_relationship_data,
    validate_create_project_status,
    validate_project_data,
)

from .skill import SkillSerializer
from .specialization import SpecializationSerializer
from .user import (
    UserAuthorSerializer,
    UserAuthorShortSerializer,
    UserBaseSerializer,
    UserParticipantSerializer,
)
from .work_format import WorkFormatSerializer


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
        """Валидация всех данных для создания проекта.

        Вызывает validate_project_data, которая проверяет:
        - количество проектов у пользователя
        - даты начала и окончания
        - количество навыков
        - существование skills, specializations, work formats

        Отдельно валидирует статус проекта.
        """
        status_project = data.get('status_project')
        if status_project:
            validate_create_project_status(status_project)

        user = self.context['request'].user
        return validate_project_data(data, user)

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
        return get_project_with_relations(project.project_id)


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
