from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from users.models import Skill, Specialization

from .models import Project, WorkFormat

User = get_user_model()


class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор навыков."""

    class Meta:
        model = Skill
        fields = ('skill_id', 'name')


class SpecializationSerializer(serializers.ModelSerializer):
    """Сериализатор специализаций."""

    class Meta:
        model = Specialization
        fields = ('spec_id', 'name')


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

    def _extract_relationship_data(self, validated_data: dict) -> dict:
        """Извлекает данные связей и возвращает их в словаре."""
        return {
            'skills': validated_data.pop('skills', []),
            'specializations': validated_data.pop('specializations', []),
            'formats': validated_data.pop('project_format', []),
        }

    def _validate_skills(self, skills_data: list) -> list:
        """Валидирует существование навыков и возвращает объекты."""
        if not skills_data:
            return []
        skill_ids = [item.get('skill_id') for item in skills_data]
        if None in skill_ids:
            raise serializers.ValidationError(
                'В данных навыков отсутствует поле "skill_id"',
            )
        existing_skills = Skill.objects.filter(skill_id__in=skill_ids)
        existing_ids = {str(skill.skill_id) for skill in existing_skills}
        missing_ids = set(skill_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f'Навык(и) с ID {", ".join(missing_ids)} не найден(ы)',
            )
        return list(existing_skills)

    def _validate_specializations(self, specializations_data: list) -> list:
        """Валидирует существование специализаций и возвращает объекты."""
        if not specializations_data:
            return []
        spec_ids = [item.get('spec_id') for item in specializations_data]
        if None in spec_ids:
            raise serializers.ValidationError(
                'В данных специализаций отсутствует поле "spec_id"',
            )
        existing_specs = Specialization.objects.filter(spec_id__in=spec_ids)
        existing_ids = {str(spec.spec_id) for spec in existing_specs}
        missing_ids = set(spec_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f'Специализация(и) с ID '
                f'{", ".join(missing_ids)} не найдена(ы)',
            )
        return list(existing_specs)

    def _validate_formats(self, formats_data: list) -> list:
        """Валидирует существование форматов работы и возвращает объекты."""
        if not formats_data:
            return []
        format_ids = formats_data
        existing_formats = WorkFormat.objects.filter(format_id__in=format_ids)
        existing_ids = {str(fmt.format_id) for fmt in existing_formats}
        missing_ids = set(format_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f'Формат(ы) работы с ID {", ".join(missing_ids)} не найден(ы)',
            )
        return list(existing_formats)

    def _add_relationships_in_project(
        self,
        instance: Project,
        relationship_data: dict,
    ) -> None:
        """Присваивает связанные объекты проекту."""
        skills = self._validate_skills(relationship_data['skills'])
        specializations = self._validate_specializations(
            relationship_data['specializations'],
        )
        formats = self._validate_formats(relationship_data['formats'])
        if skills:
            instance.skills.set(skills)
        if specializations:
            instance.specializations.set(specializations)
        if formats:
            instance.project_format.set(formats)

    @transaction.atomic
    def create(self, validated_data: dict) -> Project:
        """Метод для валидации и создания проекта."""
        relationship_data = self._extract_relationship_data(validated_data)
        user = self.context['request'].user
        validated_data['author'] = user
        if validated_data.get('status_project') == 'published':
            validated_data['published_at'] = timezone.now()
        project = Project.objects.create(**validated_data)
        self._add_relationships_in_project(project, relationship_data)
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
        if user.is_authenticated:
            return user in project.likes.all()
        return False

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
