from typing import Any, List

from django.db import transaction
from django.db.models import Q, QuerySet

from core.constants.projects import (
    ARCHIVED,
    BLOCKED,
    DRAFT,
    PUBLISHED,
    RECRUITING_CLOSED,
)
from users.models import User as UserModel

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
                    'Если автор: все проекты (кроме archived).'
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
    create=extend_schema(tags=['Проекты'], summary='Создать проект'),
    retrieve=extend_schema(
        tags=['Проекты'],
        summary='Просмотр подробной информации о проекте',
    ),
    partial_update=extend_schema(
        tags=['Проекты'],
        summary='Редактировать проект',
    ),
    destroy=extend_schema(tags=['Проекты'], summary='Мягкое удаление проекта'),
    recommendations=extend_schema(
        tags=['Проекты'],
        summary='Персональные рекомендации проектов',
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
    http_method_names = ['get', 'post', 'patch', 'delete']
    lookup_field = 'project_id'
    ordering = ['-published_at']
    pagination_class = CustomProjectPagination

    filter_backends = [DjangoFilterBackend]
    filterset_class = ProjectFilter

    def get_queryset(self) -> QuerySet[Project]:
        """Оптимизированный queryset с предзагрузкой связанных данных.

        Логика фильтрации по статусу в зависимости от action:
        - list (без my_project): исключаем DRAFT, BLOCKED, ARCHIVED.
        - list (с my_project): фильтр my_project сам управляет видимостью.
        - retrieve (автор-employer): свои проекты + PUBLISHED,
          RECRUITING_CLOSED.
        - retrieve (обычный пользователь): только PUBLISHED,
          RECRUITING_CLOSED.
        - Остальные действия: все проекты.
        """
        qs = get_optimized_project_queryset()

        if self.action == 'list':
            # Для list без my_project исключаем черновики, заблокированные,
            # архивные. Если my_project=true — filter_my_project сам управляет.
            if not self.request.query_params.get('my_project'):
                qs = qs.exclude(
                    status_project__in=[DRAFT, BLOCKED, ARCHIVED],
                )
            return qs

        if self.action == 'retrieve':
            user = self.request.user
            if (
                user.is_authenticated
                and user.projects_relation
                == UserModel.ProjectsRelationChoices.EMPLOYER
            ):
                return qs.filter(
                    Q(author=user) |
                    Q(status_project__in=[PUBLISHED, RECRUITING_CLOSED]),
                )
            return qs.filter(
                status_project__in=[PUBLISHED, RECRUITING_CLOSED],
            )

        return qs

    def get_permissions(self) -> List[BasePermission]:
        """Переопределяем разрешения для разных действий.

        - list — AllowAny.
        - create, update, partial_update, destroy — IsEmployer.
        """
        match self.action:
            case 'list':
                return [AllowAny()]
            case 'create' | 'update' | 'partial_update' | 'destroy':
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
        - Проверка прав осуществляется через CanArchiveProject
          (has_object_permission).
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
    def update(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Обновление проекта, возможно  частичное."""
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
        responses=ProjectShortSerializer(many=True),
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
        """Эндпоинт для получения рекомендаций по проектам."""
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 20))
        user = request.user
        user_skills = list(user.skills.all())
        if not user_skills:
            paginator = self.pagination_class()
            paginator.page_size = limit
            paginator.paginate_queryset([], request)
            return paginator.get_paginated_response({
                'items': [],
                'page': page,
                'limit': limit,
            })
        recommended_projects = get_recommended_projects_queryset(user)
        # Применяем пагинацию с использованием кастомного пагинатора
        paginator = self.pagination_class()
        paginator.page_size = limit
        paginated_projects = paginator.paginate_queryset(
            recommended_projects,
            request,
        )
        # Сериализация проектов
        project_serializer = ProjectShortSerializer(
            paginated_projects,
            many=True,
            context={'request': request},
        )
        return paginator.get_paginated_response({
            'items': project_serializer.data,
            'page': page,
            'limit': limit,
        })
