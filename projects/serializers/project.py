from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.constants.projects import (
    ARCHIVED,
    DRAFT,
    PUBLISHED,
    RECRUITING_CLOSED,
)
from projects.models import Project
from projects.selectors import get_project_with_relations
from projects.validators import (
    add_relationships_to_project,
    extract_relationship_data,
    validate_create_project_status,
    validate_project_data,
    validate_update_project_status,
)

from .skill import SkillSerializer
from .specialization import SpecializationSerializer
from .user import (
    UserAuthorSerializer,
    UserAuthorShortSerializer,
    UserBaseSerializer,
)
from .work_format import WorkFormatSerializer

User = get_user_model()


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
    is_liked_by_me = serializers.BooleanField(
        read_only=True,
        default=False,
        help_text='Лайкнул ли проект текущий пользователь (аннотация БД).',
    )
    participants_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'project_id', 'title', 'short_desc', 'location',
            'status_project', 'published_at', 'participants_count',
            'is_liked_by_me', 'skills',
        ]

    def get_participants_count(self, project: Project) -> int:
        """Получаем количество участников проекта.

        Использует prefetch_related('participants') — без доп. запроса.
        """
        return project.participants.count()


class ProjectDetailSerializer(ProjectShortSerializer):
    """Сериализатор детальной карточки проекта.

    Логика видимости полей в зависимости от роли пользователя.
    """

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

    def _is_author_employer(self, project: Project) -> bool:
        """Проверяет, является ли текущий пользователь автором-нанимателем.

        Возвращает True, если пользователь:
        - является автором проекта
        - имеет роль projects_relation = EMPLOYER
        """
        requesting_user = self.context.get('request').user
        return (
            project.author == requesting_user
            and requesting_user.projects_relation
            == User.ProjectsRelationChoices.EMPLOYER
        )

    def get_likes_count(self, project: Project) -> int:
        """Получаем количество лайков проекта.

        Использует prefetch_related('likes') — без дополнительного запроса.
        """
        return project.likes.count()

    def get_participants(self, project: Project) -> list:
        """Получает инфу об участниках проекта.

        - Автор-наниматель видит ID, full_name, аватар,
          email, phone участников.
        - Участник и обычный пользователь видят только
          ID, full_name, аватар участников.
        """
        is_author_employer = self._is_author_employer(project)
        serializer_class = (
            UserAuthorSerializer if is_author_employer else UserBaseSerializer
        )
        participants_qs = project.participants.select_related('user')
        if is_author_employer:
            participants_qs = participants_qs.exclude(user=project.author)
        users = [p.user for p in participants_qs]
        return serializer_class(
            users,
            many=True,
        ).data

    def get_author(self, project: Project) -> dict:
        """Метод для показа информации об авторе проекта.

        - Автор-наниматель видит полную информацию о себе (email, phone).
        - Участник проекта видит полную информацию об авторе (email, phone).
        - Обычный пользователь видит краткую информацию.

        Использует аннотацию is_participant из get_optimized_project_queryset
        — без дополнительного запроса к БД.
        """
        is_author_employer = self._is_author_employer(project)
        is_participant = getattr(project, 'is_participant', False)
        serializer_class = (
            UserAuthorSerializer
            if is_author_employer or is_participant
            else UserAuthorShortSerializer
        )
        return serializer_class(project.author).data

    def get_full_desc(self, project: Project) -> str | None:
        """Условное поле: показывается только для автора и участников.

        Использует аннотацию is_participant из get_optimized_project_queryset
        """
        is_author_employer = self._is_author_employer(project)
        is_participant = getattr(project, 'is_participant', False)
        if is_author_employer or is_participant:
            return project.full_desc
        return None

    def to_representation(self, instance: Project) -> dict:
        """Удаляет full_desc из ответа, если пользователь не участник/автор.

        SerializerMethodField всегда добавляет поле в вывод.
        Перехватываем вывод и убираем ключ, если значение None.
        """
        data = super().to_representation(instance)
        if data.get('full_desc') is None:
            data.pop('full_desc', None)
        return data


class ProjectArchiveSerializer(serializers.Serializer):
    """Сериализатор для архивирования проекта."""

    def save(self, **kwargs: dict) -> Project:
        """Архивирует проект: переводит в статус 'archived'."""
        project = self.instance
        project.status_project = ARCHIVED
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
    project_format = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Project
        fields = [
            'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status_project', 'skills', 'specializations', 'project_format',
        ]
        extra_kwargs = {
            'title': {'required': False},
            'short_desc': {'required': False},
            'full_desc': {'required': False},
            'location': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False},
            'status_project': {'required': False},
        }

    def validate_status_project(self, status_project: str) -> str:
        """Валидация статуса проекта."""
        if status_project is None:
            return status_project
        valid_statuses = [DRAFT, PUBLISHED, RECRUITING_CLOSED]
        if status_project not in valid_statuses:
            raise serializers.ValidationError(
                f'Статус должен быть одним из: {", ".join(valid_statuses)}.',
            )
        # Проверяем правильно ли переключаем статус проекта.
        project = self.instance
        if project is not None:
            validate_update_project_status(
                current_status=project.status_project,
                new_status=status_project,
            )
        return status_project

    @transaction.atomic
    def update(self, project: Project, validated_data: dict) -> Project:
        """Метод для обновления проекта."""
        relationship_data = extract_relationship_data(validated_data)
        # Если статус меняется с draft → published, проставляем дату публикации
        new_status = validated_data.get('status_project')
        if (
            new_status == PUBLISHED
            and project.status_project == DRAFT
            and project.published_at is None
        ):
            validated_data['published_at'] = timezone.now()
        for attr, value in validated_data.items():
            setattr(project, attr, value)
        project.save(update_fields=validated_data.keys())
        add_relationships_to_project(project, relationship_data)
        return get_project_with_relations(project.project_id)


class ProjectUpdateResponseSerializer(serializers.ModelSerializer):
    """Сериализатор для формирования ответа после обновления проекта."""

    status_project = serializers.CharField(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    specializations = SpecializationSerializer(many=True, read_only=True)
    project_format = WorkFormatSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'project_id', 'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status_project', 'published_at', 'created_at',
            'skills', 'specializations', 'project_format',
        ]
