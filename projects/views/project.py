from typing import Any, List

from django.db import transaction
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response as DRFResponse
from rest_framework.viewsets import ModelViewSet

from projects.filters import ProjectFilter
from projects.models import Project
from projects.paginations import CustomProjectPagination
from projects.permissions import IsEmployer
from projects.selectors import (
    get_optimized_project_queryset,
    get_recommended_projects_queryset,
    get_visible_projects_for_list,
    get_visible_projects_for_retrieve,
)
from projects.serializers import (
    ProjectArchiveSerializer,
    ProjectCreateSerializer,
    ProjectCreationResponseSerializer,
    ProjectDetailSerializer,
    ProjectLikeResponseSerializer,
    ProjectShortSerializer,
    ProjectUpdateResponseSerializer,
    ProjectUpdateSerializer,
)
from projects.services import toggle_project_like


@extend_schema_view(
    list=extend_schema(
        tags=['Проекты'],
        summary='Список проектов с возможностью фильтрации',
        description=(
            'Возвращает список проектов (краткое описание) с пагинацией.'
            'Эндпоинт доступен всем пользователям.'
        ),
        parameters=[
            # Формат работы
            OpenApiParameter(
                name='format_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID форматов через запятую',
                required=False,
            ),
            # Специализации
            OpenApiParameter(
                name='spec_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID специализаций через запятую',
                required=False,
            ),
            # Навыки/теги
            OpenApiParameter(
                name='skills_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID навыков через запятую',
                required=False,
            ),
            # Длительность: мин. дней
            OpenApiParameter(
                name='duration_min',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Минимальная длительность в днях (от 7 до 365)',
                required=False,
            ),
            # Длительность: макс. дней
            OpenApiParameter(
                name='duration_max',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Максимальная длительность в днях (от 7 до 365)',
                required=False,
            ),
            # Оператор длительности
            OpenApiParameter(
                name='duration_operator',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Оператор: less (меньше), '
                    'greater (больше), '
                    'between (между)'
                ),
                required=False,
                enum=['less', 'greater', 'between'],
            ),
            # Текстовый поиск
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Поиск по title и short_desc',
                required=False,
            ),
            # Статус проекта
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Статус проекта: draft, published, recruiting_closed. '
                    'При фильтрации по специализации проекты со статусом '
                    'recruiting_closed не отображаются.'
                ),
                required=False,
                enum=['draft', 'published', 'recruiting_closed'],
            ),
            # Сортировка
            OpenApiParameter(
                name='sort_by',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Сортировка: like (по лайкам),'
                    'published_at (по дате публикации), '
                    'relevance (по релевантности — только при наличии search).'
                    'По умолчанию: published_at.'
                ),
                required=False,
                enum=['like', 'relevance', 'published_at'],
            ),
            # Проекты пользователя
            OpenApiParameter(
                name='my_project',
                type=bool,
                location=OpenApiParameter.QUERY,
                description=(
                    'Проекты, где пользователь — автор или участник. '
                    'Если автор: все проекты (кроме - blocked).'
                    'Если участник: только published или recruiting_closed.'
                ),
                required=False,
            ),
            # Пагинация: номер страницы
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Номер страницы (по умолчанию 1)',
                required=False,
            ),
            # Пагинация: записей на странице
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Записей на странице (по умолчанию 20, макс 100)',
                required=False,
                examples=[
                    OpenApiExample('Default', value=20),
                    OpenApiExample('Max', value=100),
                ],
            ),
            # Бесконечный скролл
            OpenApiParameter(
                name='load_more',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Флаг подгрузки (бесконечный скролл)',
                required=False,
            ),
        ],
        responses={
            200: ProjectShortSerializer(many=True),
        },
    ),
    create=extend_schema(
        tags=['Проекты'],
        summary='Создать проект',
        description=(
            'Эндпоинт для создания нового проекта. '
            'Доступ только для Нанимателей (employer).\n\n'
            'Для создания проекта необходимо заполнить все данные.'
        ),
    ),
    retrieve=extend_schema(
        tags=['Проекты'],
        summary='Просмотр подробной информации о проекте',
        description=(
            'Эндпоинт для просмотра подробной карточки проекта. '
            'Информация о проекте зависит от роли пользователя, '
            'а также от того учавствует он в проекте или нет.\n\n'
            ' - Для обычных пользователей поля full_desc, author.email, '
            'author.phone, participants отсутствуют в ответе.\n\n'
            ' - Для автора проекта в объекте participants дополнительно '
            'возвращаются контакты участников (email, phone).\n\n'
            ' - Для участника проекта дополнительно возвращаются'
            ' контактные данные автора проекта.\n\n'
            ' - Доступно для аутентифицированного пользователя'
        ),
    ),
    partial_update=extend_schema(
        tags=['Проекты'],
        summary='Редактировать проект',
        description=(
            'Эндпоинт для частичного обновления проекта.\n\n'
            ' - Доступен только пользователю Нанимателю (employer)\n\n'
            ' - Обновить можно статус проекта:\n\n'
            '- - DRAFT -> PUBLISHED\n\n'
            '- - PUBLISHED -> RECRUITING_CLOSED\n\n'
            '- - RECRUITING_CLOSED -> PUBLISHED\n\n'
            'Для удаления проекта используется отдельный эндпоинт:\n\n'
            '/api/v1/projects/{project_id}/'
        ),
    ),
    destroy=extend_schema(tags=['Проекты'], summary='Мягкое удаление проекта'),
    recommendations=extend_schema(
        tags=['Проекты'],
        summary='Персональные рекомендации проектов',
        description=(
            'Эндпоинт для получения персональных рекомендаций проектов.\n\n'
            'Доступен только Работнику (worker).\n\n'
            'Фильтрует проекты в зависимости от навыков пользователя:\n\n'
            ' - Если пользователь не указал навыки - '
            'возвращается пустой список.\n\n'
            ' - Нет проектов с совпадающими навыками - '
            'возвращаются пустой список.\n\n'
            ' - Пользователь уже участвует в проекте - '
            'проект исключаентся из рекомендаций.\n\n'
            ' - Пользователь является автором проекта - '
            'проект исключается из рекомендаций.\n\n'
        ),
        parameters=[
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Номер страницы (по умолчанию 1)',
                required=False,
                examples=[
                    OpenApiExample('Default', value=1),
                    OpenApiExample('Custom', value=2),
                ],
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Записей на странице (по умолчанию 20, макс 100)',
                required=False,
                examples=[
                    OpenApiExample('Default', value=20),
                    OpenApiExample('Max', value=100),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='ProjectRecommendationsResponse',
                    fields={
                        'items': ProjectShortSerializer(many=True),
                        'total': serializers.IntegerField(),
                        'has_more': serializers.BooleanField(),
                    },
                ),
                description='Успешный ответ с рекомендациями проектов',
            ),
        },
        examples=[
            OpenApiExample(
                'Success',
                summary='Успешный ответ',
                value={
                    'items': [],
                    'total': 0,
                    'has_more': False,
                },
            ),
        ],
    ),
)
class ProjectViewSet(ModelViewSet):
    """Вьюсет для работы с проектами."""

    permission_classes = (IsAuthenticated,)
    http_method_names = ('get', 'post', 'patch', 'delete')
    lookup_field = 'project_id'
    ordering = ('-published_at',)
    pagination_class = CustomProjectPagination

    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProjectFilter

    def get_queryset(self) -> QuerySet[Project]:
        """Оптимизированный queryset с предзагрузкой связанных данных.

        Аннотирует is_liked_by_me, is_participant, participants_count,
        likes_count через подзапросы на уровне БД — без N+1.

        Логика видимости в зависимости от action вынесена в selectors:
        - list (без my_project): get_visible_projects_for_list
        - retrieve: get_visible_projects_for_retrieve
        """
        user = self.request.user
        qs = get_optimized_project_queryset(user=user)
        if self.action == 'list':
            my_project = self.request.query_params.get('my_project')
            if not my_project or my_project.lower() == 'false':
                qs = get_visible_projects_for_list(qs)
            return qs
        if self.action == 'retrieve':
            return get_visible_projects_for_retrieve(qs, user)
        return qs

    def get_permissions(self) -> List[BasePermission]:
        """Переопределяем разрешения для разных действий.

        - list — AllowAny.
        - create, partial_update, destroy — IsEmployer.
        """
        match self.action:
            case 'list':
                return [AllowAny()]
            case 'create' | 'partial_update' | 'destroy':
                return [IsEmployer()]
            case _:
                return super().get_permissions()

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Динамический выбор сериализатора в зависимости от действия."""
        match self.action:
            case 'retrieve':
                return ProjectDetailSerializer
            case 'create':
                return ProjectCreateSerializer
            case 'destroy':
                return ProjectArchiveSerializer
            case 'list' | 'recommendations':
                return ProjectShortSerializer
            case 'partial_update':
                return ProjectUpdateSerializer
            case _:
                return ProjectDetailSerializer

    def create(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Создание проекта."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        return DRFResponse(
            ProjectCreationResponseSerializer(project).data,
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def destroy(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Переводит проект в статус 'archived'. (мягкое удаление).

        - Доступ только для автора-нанимателя, админа или суперюзера.
        """
        project = self.get_object()
        serializer = self.get_serializer(
            instance=project,
            context={'request': request},
        )
        serializer.save()
        return DRFResponse(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=['Проекты'],
        summary='Лайк/снятие лайка проекта',
        request=None,
        responses={
            200: ProjectLikeResponseSerializer,
            400: OpenApiResponse(
                description=(
                    'Нельзя лайкнуть свой проект '
                    'или проект с текущим статусом.'
                ),
            ),
        },
    )
    @action(detail=True, methods=['post'], url_path='like')
    @transaction.atomic
    def like(self, request: Request, *args: Any, **kwargs: Any) -> DRFResponse:
        """Эндпоинт для постановки/снятия лайка проекту."""
        project = self.get_object()
        try:
            result = toggle_project_like(project, request.user)
        except ValueError as e:
            return DRFResponse(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return DRFResponse(
            ProjectLikeResponseSerializer(result).data,
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def partial_update(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Частичное обновление проекта (PATCH)."""
        project = self.get_object()
        serializer = self.get_serializer(
            instance=project,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        return DRFResponse(
            ProjectUpdateResponseSerializer(project).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['Проекты'],
        summary='Персональные рекомендации проектов',
        description=(
            'Фильтрация проектов в зависимиости от навыков пользователя'
        ),
        parameters=[
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Номер страницы (по умолчанию 1)',
                required=False,
                examples=[
                    OpenApiExample('Default', value=1),
                ],
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Записей на странице (по умолчанию 20, макс 100)',
                required=False,
                examples=[
                    OpenApiExample('Default', value=20),
                    OpenApiExample('Max', value=100),
                ],
            ),
        ],
        responses={
            200: inline_serializer(
                name='RecommendationsResponse',
                fields={
                    'items': ProjectShortSerializer(many=True),
                    'total': serializers.IntegerField(),
                    'has_more': serializers.BooleanField(),
                },
            ),
        },
        examples=[
            OpenApiExample(
                'Success',
                summary='Успешный ответ',
                value={
                    'items': [],
                    'total': 0,
                    'has_more': False,
                },
            ),
        ],
    )
    @action(detail=False, methods=['get'], url_path='recommendations')
    def recommendations(
        self,
        request: Request,
    ) -> DRFResponse:
        """Эндпоинт для получения рекомендаций по проектам.

        На основе навыков пользователя находит проекты со статусом PUBLISHED,
        сортирует по убыванию количества совпадающих навыков (релевантность).

        - Если у пользователя нет навыков — пустой список (200 OK).
        - Исключаются проекты автора и проекты, где пользователь участник.
        """
        user = request.user
        recommended_projects = get_recommended_projects_queryset(user)
        page = self.paginate_queryset(recommended_projects)
        serializer = ProjectShortSerializer(
            page,
            many=True,
            context={'request': request},
        )
        return self.get_paginated_response(serializer.data)
