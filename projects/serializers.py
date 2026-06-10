from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.constants.projects import (
    ALLOWED_STATUSED_FOR_LIKE,
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
from users.models import Skill, Specialization

from .models import (
    Project,
    ProjectLike,
    ProjectParticipant,
    Response,
    WorkFormat,
)
from .selectors import (
    add_user_to_project_participants,
    create_response,
    get_project_or_404,
    get_project_with_relations,
    get_user_or_404,
)
from .validators import (
    add_relationships_to_project,
    extract_relationship_data,
)

User = get_user_model()


class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения и привязки навыков пользователя."""

    class Meta:
        model = Skill
        fields = ('skill_id', 'name')
        read_only_fields = ('name',)
        extra_kwargs = {
            'skill_id': {'read_only': False},
        }


class SpecializationSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения специализаций."""

    class Meta:
        model = Specialization
        fields = ('spec_id', 'name')
        read_only_fields = ('name',)
        extra_kwargs = {
            'spec_id': {'read_only': False},
        }


class WorkFormatSerializer(serializers.ModelSerializer):
    """Сериализатор форматов работы."""

    class Meta:
        model = WorkFormat
        fields = ('format_id', 'name')
        read_only_fields = ('name',)
        extra_kwargs = {
            'format_id': {'read_only': False},
        }


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


# TODO [PROJECTS-14/24]: UserParticipantSerializer — полный дубликат UserAuthorSerializer.
#   Класс (строка 120) наследует UserAuthorSerializer и не добавляет никаких
#   изменений (pass). При этом используется в get_participants (строка 266)
#   как отдельный сериализатор. Нужно либо удалить и использовать
#   UserAuthorSerializer напрямую, либо добавить отличия.
class UserParticipantSerializer(UserAuthorSerializer):
    """Сериализатор для участника проекта — те же поля, что у автора."""

    pass


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания проекта."""

    # TODO [PROJECTS-15/24]: Добавить валидацию, что end_date не в прошлом.
    #   Сейчас проверяется только start_date > end_date (строка 172),
    #   но нет проверки, что end_date >= today().
    #   Проект с end_date в прошлом не имеет смысла.

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

    # TODO [PROJECTS-16/24]: Заменить ручную проверку лайка на аннотацию через Exists.
    #   Проблема: get_is_liked_by_me (строка 225) делает отдельный SQL-запрос
    #   ProjectLike.objects.filter(user=user, project=project).exists()
    #   для каждого проекта в списке. Даже при prefetch_related('likes')
    #   этот метод НЕ использует prefetched данные.
    #
    #   Решение через стандартный DRF + Subquery/Exists:
    #   1. В get_optimized_project_queryset (selectors.py) добавить аннотацию:
    #      from django.db.models import Exists, OuterRef
    #
    #      def get_optimized_project_queryset(user=None):
    #          qs = Project.objects.select_related('author').prefetch_related(...)
    #          if user and user.is_authenticated:
    #              qs = qs.annotate(
    #                  is_liked_by_me=Exists(
    #                      ProjectLike.objects.filter(
    #                          user=user,
    #                          project=OuterRef('project_id'),
    #                      ),
    #                  ),
    #              )
    #          return qs
    #
    #   2. В ProjectShortSerializer заменить SerializerMethodField на BooleanField:
    #      is_liked_by_me = serializers.BooleanField(read_only=True, default=False)
    #
    #   Преимущества:
    #     - Один SQL-запрос вместо N+1.
    #     - Аннотация выполняется на уровне БД — максимальная производительность.
    #     - BooleanField вместо SerializerMethodField — меньше кода.
    #     - Не нужно prefetch_related('likes') для этой проверки.
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

    # TODO [PROJECTS-17/24]: Заменить ручную проверку членства в participants
    #   на аннотацию через Exists.
    #   Проблема: get_participants (строка 271), get_author (строка 289),
    #   get_full_desc (строка 303) многократно вызывают
    #   requesting_user in project.participants.all(), что:
    #     1. Загружает ВСЕХ участников в память (O(n) по памяти).
    #     2. Делает полное сканирование списка (O(n) по времени).
    #     3. Выполняется 3 раза для одного запроса.
    #
    #   Решение через стандартный DRF + аннотация:
    #   1. В get_optimized_project_queryset добавить аннотацию членства:
    #      from django.db.models import Exists, OuterRef, Q, Value, BooleanField
    #
    #      def get_optimized_project_queryset(user=None):
    #          qs = Project.objects.select_related('author').prefetch_related(...)
    #          if user and user.is_authenticated:
    #              qs = qs.annotate(
    #                  is_participant=Exists(
    #                      ProjectParticipant.objects.filter(
    #                          project=OuterRef('project_id'),
    #                          user=user,
    #                      ),
    #                  ),
    #              )
    #          return qs
    #
    #   2. В ProjectDetailSerializer заменить проверки:
    #      def get_author(self, project):
    #          is_participant = getattr(project, 'is_participant', False)
    #          if is_participant:
    #              return UserAuthorSerializer(project.author).data
    #          return UserAuthorShortSerializer(project.author).data
    #
    #      def get_full_desc(self, project):
    #          is_participant = getattr(project, 'is_participant', False)
    #          if is_participant:
    #              return project.full_desc
    #          return None
    #
    #   Преимущества:
    #     - Одна аннотация вместо трёх загрузок всех участников.
    #     - Проверка на уровне БД через EXISTS (O(1)).
    #     - Не загружает лишние данные в память.
    #     - Убирает дублирование логики проверки членства.
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


# TODO [PROJECTS-18/24]: Заменить ручную toggle-логику лайков на стандартный
#   ViewSet action с GenericRelation или отдельный LikeAPIView.
#   Проблема: ProjectLikeSerializer.toggle_like() (строка 342) вручную:
#     1. Проверяет существование лайка через .exists().
#     2. Удаляет или создаёт лайк.
#     3. Считает количество лайков через отдельный запрос.
#   Это дублируется в QuestionViewSet.like и AnswerViewSet.like.
#
#   Решение 1 — через GenericRelation + F():
#   1. В модель Project добавить GenericRelation:
#      from django.contrib.contenttypes.fields import GenericRelation
#
#      class Project(models.Model):
#          likes_count = models.IntegerField(default=0)
#
#   2. В модели ProjectLike использовать GenericForeignKey:
#      from django.contrib.contenttypes.fields import GenericForeignKey
#
#      class ProjectLike(models.Model):
#          content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
#          object_id = models.UUIDField()
#          content_object = GenericForeignKey('content_type', 'object_id')
#
#   3. В action like() использовать F() для атомарного инкремента:
#      @action(detail=True, methods=['post'])
#      def like(self, request, pk=None):
#          project = self.get_object()
#          user = request.user
#          like, created = ProjectLike.objects.get_or_create(
#              user=user, project=project,
#          )
#          if not created:
#              like.delete()
#              Project.objects.filter(pk=project.pk).update(
#                  likes_count=F('likes_count') - 1,
#              )
#              liked = False
#          else:
#              Project.objects.filter(pk=project.pk).update(
#                  likes_count=F('likes_count') + 1,
#              )
#              liked = True
#          project.refresh_from_db()
#          return Response({
#              'liked': liked,
#              'likes_count': project.likes_count,
#          })
#
#   Решение 2 — через отдельный LikeAPIView (если GenericRelation не подходит):
#   class ProjectLikeToggleView(APIView):
#       """Единый View для toggle-лайка любого контента."""
#       permission_classes = [IsAuthenticated]
#
#       def post(self, request, content_type_id, object_id):
#           model_class = {
#               'project': Project,
#               'question': Question,
#               'answer': Answer,
#           }.get(content_type_id)
#           if not model_class:
#               return Response({'error': 'Invalid content type'}, status=400)
#
#           obj = get_object_or_404(model_class, pk=object_id)
#           like_model = {
#               Project: ProjectLike,
#               Question: QuestionLike,
#               Answer: AnswerLike,
#           }[model_class]
#
#           like, created = like_model.objects.get_or_create(
#               user=request.user,
#               **{content_type_id: obj},
#           )
#           if not created:
#               like.delete()
#           return Response({
#               'liked': created,
#               'likes_count': like_model.objects.filter(
#                   **{content_type_id: obj},
#               ).count(),
#           })
#
#   Преимущества:
#     - Единая логика для всех типов лайков (Project, Question, Answer).
#     - F()-инкремент атомарен — нет гонки данных.
#     - Денормализованное likes_count в модели — не нужно считать каждый раз.
#     - Убирается дублирование кода в 3-х местах.
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

    # TODO [PROJECTS-19/24]: Несоответствие имени поля 'formats' vs 'project_format'.
    #   В ProjectCreateSerializer поле называется 'project_format' (строка 141),
    #   а здесь — 'formats' (строка 347). При этом extract_relationship_data
    #   (validators.py:107) ожидает ключ 'project_format', а не 'formats'.
    #   Из-за этого:
    #   1. pop('project_format') не находит данные — relationship_data пустой
    #   2. 'formats' остаётся в validated_data
    #   3. hasattr(project, 'formats') → False → поле игнорируется
    #   4. Форматы работы не обновляются
    #   Решение: переименовать 'formats' → 'project_format' в этом сериализаторе.

    # TODO [PROJECTS-20/24]: Отсутствует валидация дат в ProjectUpdateSerializer.
    #   В ProjectCreateSerializer есть validate (строка 169), который проверяет
    #   start_date > end_date. В этом сериализаторе такой проверки нет.
    #   При обновлении можно передать end_date раньше start_date.
    #   Решение: добавить метод validate с той же логикой.

    # TODO [PROJECTS-21/24]: Поле 'status' в validated_data не маппится в 'status_project'.
    #   extra_kwargs указывает source='status_project' (строка 380), но DRF
    #   НЕ заменяет ключ в validated_data — там будет 'status', а не 'status_project'.
    #   В update() (строка 398): hasattr(project, 'status') → False (у модели поле
    #   называется status_project). Статус не обновится.
    #   Решение: в update() обрабатывать 'status' отдельно:
    #   if 'status' in validated_data:
    #       project.status_project = validated_data.pop('status')

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

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация перед созданием инвайта."""
        project_id = self.context['project_id']
        user_id = self.context['user_id']
        project = get_project_or_404(project_id)
        user = get_user_or_404(user_id)
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
        help_text="Новый статус отклика",
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


class ProfileCardConditionalSerializer(serializers.Serializer):
    """Сериализатор профиля с условным добавлением контактов.

    Используется при фильтрации ленты откликов/приглашений.
    """

    # TODO [PROJECTS-22/24]: Несоответствие имени поля 'phone' vs 'phone_number'.
    #   В сериализаторе поле объявлено как 'phone' (строка 686), но в модели
    #   User (users/models/users.py:119) поле называется 'phone_number'.
    #   В to_representation (строка 708) данные берутся из instance.phone_number,
    #   а ключ в response будет 'phone'. Фронтенд должен знать об этом маппинге.
    #   Для консистентности стоит либо:
    #   - переименовать поле в 'phone_number' в сериализаторе, либо
    #   - добавить source='phone_number' и убрать ручное присвоение.

    user_id = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    avatar_url = serializers.URLField(required=False, allow_null=True)
    skills = serializers.SerializerMethodField()
    email = serializers.EmailField(
        read_only=True,
        required=False,
        allow_null=True,
    )
    phone = serializers.CharField(
        read_only=True,
        required=False,
        allow_null=True,
    )

    def get_skills(self, user: User) -> List:
        """Форматируем навыки в список."""
        return [skill.name for skill in user.skills.all()]

    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """Форматируем поля для ответа."""
        data = super().to_representation(instance)
        response = self.context.get('response')
        user = self.context.get('user')
        # Добавляем контакты только если:
        # response_status == 'approved'
        # текущий пользователь — автор проекта
        if (response and response.status_resp == APPROVED and
                hasattr(response, 'project') and response.project and
                response.project.author_id == user.id):
            data['email'] = instance.email
            data['phone'] = instance.phone_number
        else:
            data.pop('email', None)
            data.pop('phone', None)
        return data


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

    Для выдачи информации использует ProjectCardConditionalSerializer и
    ProfileCardConditionalSerializer.

    Автор проекта получает профили пользователей с откликами и свои отклики.
    Пользователь получает проекты где он откликнулся.
    """

    response_id = serializers.UUIDField()
    card_type = serializers.SerializerMethodField()
    response_status = serializers.CharField(source='status_resp')
    response_created_at = serializers.DateTimeField(source='created_at')

    project = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_card_type(self, instance: Any) -> str:
        """Определяем тип карточки, которую возвращаем.

        Если пользователь автор, то возвращаем profile (профили пользователей,
        которые откликнулись на проект.)
        Если пользователь участник проекта, то возвращаем project.
        """
        user = self.context.get('user')
        if hasattr(
            instance,
            'project',
        ) and instance.project and instance.project.author_id == user.id:
            return 'profile'
        return 'project'

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

    def get_profile(self, instance: Response) -> Optional[Dict[str, Any]]:
        """Получаем профили пользователей, кто откликнулся."""
        if self.get_card_type(
            instance,
        ) == 'profile' and hasattr(instance, 'user') and instance.user:
            serializer = ProfileCardConditionalSerializer(
                instance.user,
                context={
                    'user': self.context.get('user'),
                    'response': instance,
                    'request': self.context.get('request'),
                },
            )
            return serializer.data
        return None

    # TODO [PROJECTS-23/24]: Мутация данных в to_representation (строка 845).
    #   project_data['status'] = project_data.pop('status_project') изменяет
    #   исходный словарь, который может быть закеширован или переиспользован.
    #   Это может привести к багам при повторной сериализации того же объекта.
    #   Решение: создать копию project_data перед мутацией или маппить
    #   через отдельный ключ без изменения исходного словаря.
    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """Форматируем поля для ответа."""
        data = super().to_representation(instance)
        card_type = data['card_type']
        result = {
            'response_id': data['response_id'],
            'response_status': data['response_status'],
            'response_created_at': data['response_created_at'],
        }
        if card_type == 'project' and data.get('project'):
            project_data = data['project']
            if 'status_project' in project_data:
                project_data['status'] = project_data.pop('status_project')
            result.update(project_data)
        elif card_type == 'profile' and data.get('profile'):
            result.update(data['profile'])
        return result
