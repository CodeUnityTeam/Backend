import hashlib
import logging
from typing import Any

from django.core.cache import cache
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

from core.cache_mixins import CacheRetrieveMixin
from core.constants.cache import (
    CACHE_KEY_PROJECTS_PREFIX,
    PROJECT_DETAIL_CACHE_TIMEOUT,
    PROJECT_LIST_CACHE_TIMEOUT,
    PROJECT_RECOMMENDATIONS_CACHE_TIMEOUT,
)
from core.constants.projects import PAGE_SIZE
from projects.filters import ProjectFilter
from projects.models import Project, ProjectLike
from projects.paginations import CustomProjectPagination
from projects.permissions import IsEmployer, IsWorker
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
    ProjectFavoriteResponseSerializer,
    ProjectLikeResponseSerializer,
    ProjectShortSerializer,
    ProjectUpdateResponseSerializer,
    ProjectUpdateSerializer,
)
from projects.services import (
    archive_project,
    toggle_project_favorite,
    toggle_project_like,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=['Проекты'],
        summary='Список проектов с возможностью фильтрации',
        description=(
            'Возвращает список проектов (краткое описание) с пагинацией.'
            'Эндпоинт доступен всем пользователям.'
        ),
        parameters=[
            OpenApiParameter(
                name='format_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID форматов через запятую',
                required=False,
            ),
            OpenApiParameter(
                name='spec_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID специализаций через запятую',
                required=False,
            ),
            OpenApiParameter(
                name='skills_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID навыков через запятую',
                required=False,
            ),
            OpenApiParameter(
                name='duration_min',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Минимальная длительность в днях (от 7 до 365)',
                required=False,
            ),
            OpenApiParameter(
                name='duration_max',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Максимальная длительность в днях (от 7 до 365)',
                required=False,
            ),
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
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Поиск по title и short_desc',
                required=False,
            ),
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
            OpenApiParameter(
                name='favourites',
                type=bool,
                location=OpenApiParameter.QUERY,
                description=(
                    'Проекты, которые пользователь добавил в избранное. '
                    'Избранные проекты могут быть только со статусами: '
                    'published, recruiting_closed.'
                ),
                required=False,
            ),
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Номер страницы (по умолчанию 1)',
                required=False,
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
class ProjectViewSet(CacheRetrieveMixin, ModelViewSet):
    """Вьюсет для работы с проектами."""

    permission_classes = (IsAuthenticated(),)
    http_method_names = ('get', 'post', 'patch', 'delete')
    lookup_field = 'project_id'
    ordering = ('-published_at',)
    pagination_class = CustomProjectPagination
    retrieve_cache_timeout = PROJECT_DETAIL_CACHE_TIMEOUT
    retrieve_cache_key_prefix = 'projects'

    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProjectFilter

    def list(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Кэширует список проектов.

        Ключ: projects:list:{user_id}:{md5(params)}.
        user_id в ключе позволяет точечно инвалидировать кэш при лайке.
        """
        user = request.user
        query_params = request.query_params.dict()
        sorted_params = sorted(query_params.items())
        params_str = hashlib.md5(
            str(sorted_params).encode(),
        ).hexdigest()
        user_part = str(user.pk) if user.is_authenticated else 'anonymous'
        cache_key = (
            f'{CACHE_KEY_PROJECTS_PREFIX}:list:{user_part}:{params_str}'
        )
        cached_response = cache.get(cache_key)
        logger.info(
            'Запрос списка проектов: ',
            'user_id=%s, role=%s, params=%s, cache_key=%s',
            user.pk if user.is_authenticated else 'anonymous',
            user.projects_relation if user.is_authenticated else 'anonymous',
            query_params,
        )
        if cached_response is not None:
            logger.info(
                'Получен список проектов из кэша: user_id=%s',
                user_part,
            )
            return DRFResponse(cached_response)
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=PROJECT_LIST_CACHE_TIMEOUT,
            )
            logger.info(
                'Получен список проектов из БД: user_id=%s.',
                user_part,
            )
        return response

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

    def get_permissions(self) -> BasePermission:
        """Переопределяем разрешения для разных действий.

        - list — AllowAny.
        - create, partial_update, destroy — IsEmployer.
        """
        match self.action:
            case 'list':
                return (AllowAny(),)
            case 'create' | 'partial_update' | 'destroy':
                return (IsEmployer(),)
            case 'favorite':
                return (IsWorker(),)
            case _:
                return self.permission_classes

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
        logger.info(
            'Запрос на создание проекта: user_id=%s',
            request.user.pk,
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        project = serializer.instance
        return DRFResponse(
            ProjectCreationResponseSerializer(
                project,
                context={'request': request},
            ).data,
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
        logger.info(
            'Запрос на "мягкое удаление" проекта: '
            'project=%s, user=%s.',
            project.project_id,
            request.user,
        )
        archive_project(project, user=request.user)
        logger.info(
            'Изменен статус проекта на "archive": '
            'project=%s, user=%s.',
            project.project_id,
            request.user,
        )
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
        is_liked_before = ProjectLike.objects.filter(
            project=project, user=request.user,
        ).exists()
        logger.info(
            'Запрос на изменение статуса лайка для проекта: '
            'project_id=%s, user_id=%s, liked=%s',
            project.project_id,
            request.user.pk,
            is_liked_before,
        )
        result = toggle_project_like(project, request.user)
        logger.info(
            'Статус лайка изменён: project_id=%s, user_id=%s, liked=%s',
            project.project_id,
            request.user.pk,
            result['liked'],
        )
        return DRFResponse(
            ProjectLikeResponseSerializer(
                result,
                context={'request': request},
            ).data,
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
        if hasattr(request.data, 'keys'):
            incoming_fields = list(request.data.keys())
        elif isinstance(request.data, list):
            incoming_fields = ['[is_list_payload]']
        else:
            incoming_fields = ['[unknown_payload]']
        logger.info(
            'Запрос на обновление проекта: project_id=%s, user_id=%s, '
            'incoming_fields=%s',
            project.project_id,
            request.user.pk,
            incoming_fields,
        )
        serializer = self.get_serializer(
            instance=project,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        logger.info(
            'Проект успешно обновлен: project_id=%s, user_id=%s, '
            'updated_fields=%s',
            project.project_id,
            request.user.pk,
            list(serializer.validated_data.keys()),
        )
        return DRFResponse(
            ProjectUpdateResponseSerializer(project).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['Проекты'],
        summary='Персональные рекомендации проектов',
        description=(
            'Фильтрация проектов в зависимости от навыков пользователя'
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
        """Персональные рекомендации проектов на основе навыков пользователя.

        Ключ: projects:recommendations:{user_id}:page:{page_number},TTL 10 мин.
        Инвалидируется при изменении профиля или создании проекта.
        """
        user = request.user
        page_number = request.query_params.get('page', 1)
        limit = request.query_params.get('limit', PAGE_SIZE)
        logger.debug(
            'Запрос персональных рекомендаций (получен): user_id=%s, page=%s, '
            'limit=%s',
            user.pk,
            page_number,
            limit,
        )
        cache_key = (
            f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:'
            f'{user.pk}:page:{page_number}:limit:{limit}'
        )
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(
                'Рекомендации получены из кэша: user_id=%s', user.pk,
            )
            return DRFResponse(cached_response)
        logger.debug('Кэш пуст, вычисление рекомендаций: user_id=%s', user.pk)
        try:
            recommended_projects = get_recommended_projects_queryset(user)
            page = self.paginate_queryset(recommended_projects)
            serializer = ProjectShortSerializer(
                page,
                many=True,
                context={'request': request},
            )
            response = self.get_paginated_response(serializer.data)
            cache.set(
                cache_key,
                response.data,
                timeout=PROJECT_RECOMMENDATIONS_CACHE_TIMEOUT,
            )
            return response
        except Exception:
            logger.exception(
                'Критическая ошибка при вычислении или пагинации рекомендаций:'
                ' user_id=%s.',
                user.pk,
            )
            raise

    @extend_schema(
        tags=['Проекты'],
        summary='Добавить в избранное/Убрать из избранного',
        request=None,
        responses={
            200: ProjectFavoriteResponseSerializer,
            400: OpenApiResponse(
                description=(
                    'Нельзя добавить свой проект в избранное '
                    'или проект с текущим статусом.'
                ),
            ),
        },
    )
    @action(detail=True, methods=['post'], url_path='favorite')
    @transaction.atomic
    def favorite(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Эндпоинт для добавления/удаления проекта из избранного."""
        project = self.get_object()
        logger.info(
            'Запрос на изменение "избранного" для '
            'проекта: project_id=%s, user_id=%s.',
            request.user.pk,
            project.project_id,
        )
        result = toggle_project_favorite(project, request.user)
        logger.info(
            'Статус избранного изменён: project_id=%s, user_id=%s, '
            'favorited=%s',
            project.project_id,
            request.user.pk,
            result['favorited'],
        )
        return DRFResponse(
            ProjectFavoriteResponseSerializer(
                result,
                context={'request': request},
            ).data,
            status=status.HTTP_200_OK,
        )
