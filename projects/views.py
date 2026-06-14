from typing import Any, List

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
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

from .filters import ProjectFilter, ResponseFeedFilter
from .models import Project, Response
from .paginations import CustomProjectPagination, CustomResponseFeedPagination
from .permissions import CanArchiveProject, IsEmployer
from .selectors import (
    get_optimized_project_queryset,
    get_recommended_projects_queryset,
    get_response_feed_queryset,
)
from .serializers import (
    FeedbackAndInvitationFeedSerializer,
    InviteUserProjectSerializer,
    ProjectArchiveSerializer,
    ProjectCreateSerializer,
    ProjectCreationResponseSerializer,
    ProjectDetailSerializer,
    ProjectLikeResponseSerializer,
    ProjectLikeSerializer,
    ProjectShortSerializer,
    ProjectUpdateResponseSerializer,
    ProjectUpdateSerializer,
    ResponseResponseCreateProjectSerializer,
    ResponseUserProjectSerializer,
    UpdateResponseStatusSerializer,
)
from .services import apply_sorting


@extend_schema_view(
    list=extend_schema(
        tags=['Проекты'],
        summary='Список проектов с возможностью фильтрации',
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
        responses=ProjectShortSerializer(many=True),
        examples=[
            OpenApiExample(
                'Success',
                summary='Успешный ответ',
                value={
                    'items': [],
                    'total': 0,
                    'page': 1,
                    'limit': 20,
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
    pagination_class = CustomProjectPagination
    lookup_field = 'project_id'
    ordering = ['-published_at']

    def get_queryset(self) -> QuerySet[Project]:
        """Оптимизированный queryset с предзагрузкой связанных данных."""
        return get_optimized_project_queryset()

    def get_permissions(self) -> List[BasePermission]:
        """Переопределяем разрешения для разных действий.

        - Для list — AllowAny, для остальных — стандартные.
        - Для create — только наниматели.
        """
        if self.action == 'list':
            return [AllowAny()]
        if self.action == 'destroy':
            return [CanArchiveProject()]
        if self.action == 'create':
            return [IsAuthenticated(), IsEmployer()]
        return super().get_permissions()

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Динамический выбор сериализатора в зависимости от действия."""
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        if self.action == 'create':
            return ProjectCreateSerializer
        if self.action == 'destroy':
            return ProjectArchiveSerializer
        if self.action in ('list', 'recommendations'):
            return ProjectShortSerializer
        if self.action == 'like':
            return ProjectLikeSerializer
        if self.action == 'partial_update':
            return ProjectUpdateSerializer
        if self.action in (
            'responses',
            'invite_user',
            'update_response_status',
        ):
            return ResponseResponseCreateProjectSerializer
        if self.action == 'responses_feed':
            return FeedbackAndInvitationFeedSerializer
        return ProjectDetailSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> DRFResponse:
        """Создание проекта."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        return DRFResponse(
            ProjectCreationResponseSerializer(project).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
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
        responses=ProjectShortSerializer(many=True),
        examples=[
            OpenApiExample(
                'Success',
                summary='Успешный ответ',
                value={
                    'items': [],
                    'total': 0,
                    'page': 1,
                    'limit': 20,
                    'has_more': False,
                },
            ),
        ],
    )
    def list(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse[Project]:
        """Список проектов с фильтрацией и сортировкой (только для list)."""
        queryset = self.get_queryset()
        filter_instance = ProjectFilter(
            request.query_params,
            queryset=queryset,
            request=request._request,
        )
        filtered_queryset = filter_instance.qs
        sort_by = request.query_params.get('sort_by', 'published_at')
        filtered_queryset = apply_sorting(
            filtered_queryset,
            sort_by,
            request.query_params.get('search'),
        )
        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = ProjectShortSerializer(
                page,
                many=True,
                context={'request': request},
            )
            return self.get_paginated_response(serializer.data)
        serializer = ProjectShortSerializer(
            filtered_queryset,
            many=True,
            context={'request': request},
        )
        return DRFResponse(serializer.data)

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
    )
    @action(detail=True, methods=['post'], url_path='like')
    @transaction.atomic
    def like(self, request: Request, *args: Any, **kwargs: Any) -> DRFResponse:
        """Эндпоинт для постановки/снятия лайка проекту."""
        project = self.get_object()
        input_serializer = ProjectLikeSerializer(
            data={'project_id': project.project_id},
            context={'request': request, 'project': project},
        )
        input_serializer.is_valid(raise_exception=True)
        result = input_serializer.toggle_like()
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
                    'page': 1,
                    'limit': 20,
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

    @extend_schema(
        tags=['Отклики'],
        summary='Откликнуться на проект',
        request=None,
    )
    @action(detail=True, methods=['post'], url_path='responses')
    @transaction.atomic
    def responses(
        self,
        request: Request,
        project_id: str | None = None,
    ) -> DRFResponse:
        """Эндпоинт для отклика пользователя на проект."""
        project = get_object_or_404(Project, project_id=project_id)
        serializer = ResponseUserProjectSerializer(
            data={},
            context={'request': request, 'project': project},
        )
        serializer.is_valid(raise_exception=True)
        response = serializer.save()
        return DRFResponse(
            ResponseResponseCreateProjectSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=['Отклики'],
        summary='Пригласить пользователя в проект.',
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='ID пользователя, которого приглашают в проект',
            ),
        ],
        request=None,
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='invite/(?P<user_id>[^/.]+)',
        url_name='invite-user',
    )
    @transaction.atomic
    def invite_user(
        self,
        request: Request,
        project_id: str,
        user_id: str,
    ) -> DRFResponse:
        """Пригласить пользователя в проект."""
        project = get_object_or_404(Project, project_id=project_id)
        if project.author != request.user:
            return DRFResponse(
                {'detail': 'У вас нет прав для приглашения в этот проект'},
                status=status.HTTP_403_FORBIDDEN,
            )
        create_serializer = InviteUserProjectSerializer(
            data={},
            context={
                'project_id': project_id,
                'user_id': user_id,
                'request': request,
            },
        )
        create_serializer.is_valid(raise_exception=True)
        response_instance = create_serializer.save()
        return DRFResponse(
            self.get_serializer(response_instance).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['Отклики'],
        summary='Изменить статус отклика для проекта.',
        parameters=[
            OpenApiParameter(
                name='response_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='ID отклика, который хотите изменить',
            ),
        ],
        examples=[
            OpenApiExample(
                name='Отозвать отклик',
                summary='Пример: пользователь отзывает свой отклик',
                description='Пользователь отменяет свой отклик на проект',
                value={'status': 'withdrawn'},
                request_only=True,
                response_only=False,
            ),
        ],
    )
    @action(
        detail=False,
        methods=['patch'],
        url_path='responses/(?P<response_id>[^/.]+)/status',
        url_name='update-response-status',
    )
    def update_response_status(
        self,
        request: Request,
        response_id: str | None = None,
    ) -> DRFResponse:
        """Изменить статус отклика/приглашения."""
        response = get_object_or_404(Response, response_id=response_id)
        serializer = UpdateResponseStatusSerializer(
            instance=response,
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        update_status = serializer.save()
        return DRFResponse(
            self.get_serializer(update_status).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['Отклики'],
        summary='Лента откликов/приглашений',
        parameters=[
            OpenApiParameter(
                name='card_type',
                description='Фильтр по типу карточек',
                required=False,
                type=str,
                enum=['all', 'project', 'profile'],
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='status',
                description='Фильтр по статусу отклика/приглашения',
                required=False,
                type=str,
                enum=['all', 'pending', 'approved', 'rejected', 'withdrawn'],
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='project_id',
                description='Фильтр по конкретному проекту',
                required=False,
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page',
                description='Номер страницы',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='limit',
                description='Количество элементов на странице',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='sort_by',
                description='Сортировка по дате создания',
                required=False,
                type=str,
                enum=['created_at'],
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='sort_order',
                description='Порядок сортировки',
                required=False,
                type=str,
                enum=['asc', 'desc'],
                location=OpenApiParameter.QUERY,
            ),
        ],
    )
    @action(detail=False, methods=['get'], url_path='responses')
    def responses_feed(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Действие для получения ленты откликов/приглашений."""
        queryset = get_response_feed_queryset(request.user)
        filterset = ResponseFeedFilter(
            request.GET,
            queryset=queryset,
            request=request,
        )
        filtered_queryset = filterset.qs
        paginator = CustomResponseFeedPagination()
        page = paginator.paginate_queryset(filtered_queryset, request)
        serializer = self.get_serializer(
            page if page is not None else filtered_queryset,
            many=True,
            context={
                'user': request.user,
                'request': request,
            },
        )
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        response = DRFResponse(serializer.data)
        response.data['applied_filters'] = {
            'card_type': request.query_params.get('card_type', 'all'),
            'status': request.query_params.get('status', 'all'),
        }
        return response

    def filter_queryset_for_responses(self, queryset: QuerySet) -> QuerySet:
        """Фильтрация для ленты откликов."""
        card_type = self.request.query_params.get('card_type', 'all')
        card_type_filter = self.request.query_params.get('status', 'all')
        if card_type == 'project':
            queryset = queryset.filter(user=self.request.user)
        elif card_type == 'profile':
            queryset = queryset.filter(project__author=self.request.user)
        if card_type_filter != 'all':
            return card_type_filter
        return queryset
