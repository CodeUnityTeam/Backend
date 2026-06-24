from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.constants.projects import (
    ARCHIVED,
    AUTHOR,
    DRAFT,
    PUBLISHED,
    RECRUITING_CLOSED,
)
from projects.models import Project
from projects.selectors import get_project_with_relations
from projects.services import add_user_to_project_participants
from projects.validators import (
    _validate_formats_by_uuid_list,
    _validate_related_ids,
    add_relationships_to_project,
    extract_relationship_data,
    validate_create_project_status,
    validate_project_data,
    validate_project_dates,
    validate_published_project_dates,
    validate_update_project_status,
)
from users.models.skills import Skill
from users.models.specializations import Specialization

from .skill import SkillSerializer
from .specialization import SpecializationSerializer
from .user import (
    UserAuthorSerializer,
    UserAuthorShortSerializer,
    UserBaseSerializer,
)
from .work_format import WorkFormatSerializer

User = get_user_model()


class SkillIdSerializer(serializers.Serializer):
    """Сериализатор для передачи skill_id в теле запроса."""

    skill_id = serializers.UUIDField(
        help_text='UUID навыка',
    )


class SpecializationIdSerializer(serializers.Serializer):
    """Сериализатор для передачи spec_id в теле запроса."""

    spec_id = serializers.UUIDField(
        help_text='UUID специализации',
    )


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания проекта."""

    skills = serializers.ListField(
        child=SkillIdSerializer(),
        write_only=True,
        required=True,
        help_text='Список навыков в формате [{"skill_id": "uuid"}]',
    )
    specializations = serializers.ListField(
        child=SpecializationIdSerializer(),
        write_only=True,
        required=True,
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
        fields = (
            'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status_project', 'skills', 'specializations', 'project_format',
        )
        extra_kwargs = {
            'title': {
                'required': True,
                'allow_blank': False,
                'error_messages': {
                    'required': 'Название обязательно для заполнения.',
                    'blank': 'Название не может быть пустым.',
                },
            },
            'short_desc': {
                'required': True,
                'allow_blank': False,
                'error_messages': {
                    'required': 'Кратное описание обязательно для заполнения.',
                    'blank': 'Краткое описание не может быть пустым.',
                },
            },
            'full_desc': {
                'required': True,
                'allow_blank': False,
                'error_messages': {
                    'required': 'Полное описание обязательно для заполнения.',
                    'blank': 'Полное описание не может быть пустым.',
                },
            },
            'location': {
                'required': True,
                'allow_blank': False,
                'error_messages': {
                    'required': 'Местоположение обязательно для заполнения.',
                    'blank': 'Местоположение не может быть пустым.',
                },
            },
            'start_date': {
                'required': False,
                'error_messages': {
                    'invalid': 'Неверный формат даты. Ожидается ГГГГ-ММ-ДД.',
                },
            },
            'end_date': {
                'required': True,
                'error_messages': {
                    'required': 'Дата окончания проекта обязательна.',
                    'invalid': 'Неверный формат даты. Ожидается ГГГГ-ММ-ДД.',
                },
            },
        }

    def validate(self, data: dict) -> dict:
        """Валидация всех данных для создания проекта.

        Вызывает validate_project_data, которая проверяет:
        - количество проектов у пользователя
        - количество навыков
        - существование skills, specializations, work formats

        Отдельно валидирует:
        - статус проекта
        - даты начала и окончания (если обе переданы)
        """
        status_project = data.get('status_project')
        if status_project:
            validate_create_project_status(status_project)
        # Валидация даты периода проекта (если обе даты переданы)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date:
            validate_project_dates(start_date, end_date)
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
        # Добавляем автора в участники проекта со статусом AUTHOR
        add_user_to_project_participants(
            project=project,
            user=user,
            status=AUTHOR,
        )
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
    participants_count = serializers.IntegerField(
        read_only=True,
        help_text='Количество участников проекта (аннотация БД).',
    )
    is_favorite_by_me = serializers.BooleanField(
        read_only=True,
        default=False,
        help_text='В избранном ли проект у текущего пользователя',
    )

    class Meta:
        model = Project
        fields = (
            'project_id',
            'title',
            'short_desc',
            'location',
            'status_project',
            'published_at',
            'participants_count',
            'is_liked_by_me',
            'is_favorite_by_me',
            'skills',
        )


class ProjectDetailSerializer(ProjectShortSerializer):
    """Сериализатор детальной карточки проекта.

    Логика видимости полей в зависимости от роли пользователя.
    """

    specializations = SpecializationSerializer(many=True, read_only=True)
    project_format = WorkFormatSerializer(many=True, read_only=True)
    likes_count = serializers.IntegerField(
        read_only=True,
        help_text='Количество лайков проекта (аннотация БД).',
    )
    participants = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    full_desc = serializers.SerializerMethodField()

    class Meta(ProjectShortSerializer.Meta):
        fields = ProjectShortSerializer.Meta.fields + (
            'full_desc', 'end_date', 'specializations',
            'project_format', 'likes_count', 'participants', 'author',
        )

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

    def get_participants(self, project: Project) -> list:
        """Получает инфу об участниках проекта.

        - Автор-наниматель видит ID, full_name, аватар,
          email, phone участников.
        - Участник и обычный пользователь видят только
          ID, full_name, аватар участников.

        Participants уже загружены через Prefetch с select_related('user')
        в get_optimized_project_queryset — без дополнительных запросов.
        """
        is_author_employer = self._is_author_employer(project)
        serializer_class = (
            UserAuthorSerializer if is_author_employer else UserBaseSerializer
        )
        participants_qs = project.participants.all()
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

        Использует аннотацию is_participant из get_optimized_project_queryset.
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
        child=SkillIdSerializer(),
        required=False,
        allow_empty=True,
        help_text='Список навыков в формате [{"skill_id": "uuid"}]',
    )
    specializations = serializers.ListField(
        child=SpecializationIdSerializer(),
        required=False,
        allow_empty=True,
        help_text='Список специализаций в формате [{"spec_id": "uuid"}]',
    )
    project_format = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text='Список форматов работы в формате ["uuid", "uuid"]',
    )

    class Meta:
        model = Project
        fields = (
            'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status_project', 'skills', 'specializations', 'project_format',
        )
        extra_kwargs = {
            'title': {'required': False},
            'short_desc': {'required': False},
            'full_desc': {'required': False},
            'location': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False},
            'status_project': {'required': False},
        }

    def validate(self, data: dict) -> dict:
        """Валидация данных при обновлении проекта.

        Три сценария валидации:

        1. Черновик → публикация (draft → published):
           - validate_project_dates — проверка дат.
           - validate_project_data — полная проверка всех обязательных полей.
             Если поле не передано в PATCH —
             подставляется текущее значение из БД.

        2. Изменение опубликованного проекта
           (published / recruiting_closed, включая смену статуса между ними):
           - validate_published_project_dates — защита start_date в прошлом,
             end_date не в прошлом, end_date не раньше start_date.
           - Обычная валидация переданных полей (skills, specializations,
             project_format).

        3. Черновик (без смены статуса):
           - validate_project_dates — если даты переданы, проверяет,
             что start_date не в прошлом, end_date не раньше start_date,
             длительность ≤ 1 год.
           - Обычная валидация переданных полей.
        """
        project = self.instance
        new_status = data.get('status_project')
        is_publishing = (
            new_status == PUBLISHED
            and project is not None
            and project.status_project == DRAFT
        )
        if is_publishing:
            start_date = data.get('start_date', project.start_date)
            end_date = data.get('end_date', project.end_date)
            if start_date and end_date:
                validate_project_dates(start_date, end_date)
            full_data = {
                'title': data.get('title', project.title),
                'short_desc': data.get('short_desc', project.short_desc),
                'full_desc': data.get('full_desc', project.full_desc),
                'location': data.get('location', project.location),
                'status_project': PUBLISHED,
                'skills': data.get('skills'),
                'specializations': data.get('specializations'),
                'project_format': data.get('project_format'),
            }
            # Если навыки/специализации/форматы не переданы — берём из БД
            if full_data['skills'] is None:
                full_data['skills'] = [
                    {'skill_id': str(s.skill_id)}
                    for s in project.skills.all()
                ]
            if full_data['specializations'] is None:
                full_data['specializations'] = [
                    {'spec_id': str(s.spec_id)}
                    for s in project.specializations.all()
                ]
            if full_data['project_format'] is None:
                full_data['project_format'] = [
                    str(f.format_id) for f in project.project_format.all()
                ]
            user = self.context['request'].user
            return validate_project_data(full_data, user)
        # Изменение опубликованного проекта или с закрытым набором
        published_statuses = (PUBLISHED, RECRUITING_CLOSED)
        if (
            project is not None
            and project.status_project in published_statuses
        ):
            validate_published_project_dates(
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                current_start_date=project.start_date,
            )
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date:
            validate_project_dates(start_date, end_date)
        self._validate_relationship_fields(data)
        return data

    def _validate_relationship_fields(self, data: dict) -> None:
        """Валидация переданных M2M-полей.

        Если поле не передано (None) — не трогает существующие связи.
        Если передан пустой список:
          - project_format — очищается (разрешено)
          - skills / specializations — ошибка (минимум 1 шт)
        """
        project_format = data.get('project_format')
        if project_format is not None:
            validated_formats = _validate_formats_by_uuid_list(project_format)
            data['_validated_formats'] = validated_formats
        skills = data.get('skills')
        if skills is not None:
            if not skills:
                raise serializers.ValidationError({
                    'skills': 'Необходимо указать хотя бы один навык.',
                })
            validated_skills = _validate_related_ids(
                skills, 'skill_id', Skill, 'навыки',
            )
            data['_validated_skills'] = validated_skills
        specializations = data.get('specializations')
        if specializations is not None:
            if not specializations:
                raise serializers.ValidationError({
                    'specializations': (
                        'Необходимо указать хотя бы одну специализацию.'
                    ),
                })
            validated_specializations = _validate_related_ids(
                specializations, 'spec_id', Specialization, 'специализации',
            )
            data['_validated_specializations'] = validated_specializations

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
        fields = (
            'project_id', 'title', 'short_desc', 'full_desc',
            'location', 'start_date', 'end_date',
            'status_project', 'published_at', 'created_at',
            'skills', 'specializations', 'project_format',
        )
