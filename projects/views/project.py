import hashlib
import logging
from typing import Any, List, Optional

from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, IntegerField, QuerySet, Value, When
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
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
from core.constants.projects import BLOCKED
from projects.filters import ProjectFilter
from projects.models import Project, ProjectLike
from projects.paginations import CustomProjectPagination
from projects.permissions import IsEmployer, IsWorker
from projects.selectors import (
    exclude_archived_blocked,
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

from .project_examples import EXAMPLE_DETAIL_RESPONSE_PROJECT
from .project_parameters import (
    PROJECT_LIST_PARAMETERS,
    PROJECT_RECOMENDATIONS_PARAMETERS,
)

logger = logging.getLogger(__name__)


def _build_list_cache_key(
    prefix: str,
    user: Any,
    query_params: Any,
) -> str | None:
    """Ключ полного упорядоченного списка ID для комбинации фильтров."""
    if not user.is_authenticated:
        return None
    pagination_params = {'page', 'limit'}
    normalized_params = sorted(
        (
            key,
            tuple(values),
        )
        for key, values in query_params.lists()
        if key not in pagination_params
    )
    params_hash = hashlib.sha256(
        repr(normalized_params).encode('utf-8'),
    ).hexdigest()
    return f'{prefix}:list:ids:{user.pk}:{params_hash}'


def _build_recommendations_cache_key(request: Request) -> str:
    """Сформировать ключ полного списка ID рекомендаций пользователя."""
    pagination_params = {'page', 'limit'}
    normalized_params = sorted(
        (key, tuple(values))
        for key, values in request.query_params.lists()
        if key not in pagination_params
    )
    params_hash = hashlib.sha256(
        repr(normalized_params).encode('utf-8'),
    ).hexdigest()
    return (
        f'{CACHE_KEY_PROJECTS_PREFIX}:recommendations:'
        f'{request.user.pk}:ids:{params_hash}'
    )


@extend_schema_view(
    list=extend_schema(
        tags=['Проекты'],
        summary='Список проектов с возможностью фильтрации',
        description=(
            'Возвращает список проектов (краткое описание) с пагинацией.'
            'Эндпоинт доступен всем пользователям.'
        ),
        parameters=PROJECT_LIST_PARAMETERS,
    ),
    create=extend_schema(
        tags=['Проекты'],
        summary='Создать проект',
        description=(
            'Эндпоинт для создания нового проекта. '
            'Доступ только для Нанимателей (employer).\n\n'
            ' - Для создания проекта необходимо заполнить все данные кроме'
            ' полного описания (full_desc) и форматов работы (project_format).'
            ' Если полное описание не заполнено, то оно заполниться кратким'
            ' описанием проекта при создании.\n\n'
            ' - Навыки, специализации, форматы работы должны выбираться из'
            ' имеющихся в БД.'
        ),
    ),
    retrieve=extend_schema(
        tags=['Проекты'],
        summary='Просмотр подробной информации о проекте',
        description=(
            'Эндпоинт для просмотра подробной карточки проекта. '
            'Информация о проекте зависит от роли пользователя, '
            'а также от того участвует он в проекте или нет.\n\n'
            ' - Для обычных пользователей поля full_desc, author.email, '
            'author.additional_contact отсутствуют в ответе.\n\n'
            ' - Для автора проекта в объекте participants дополнительно '
            'возвращаются контакты участников (email, additional_contact).\n\n'
            ' - Для участника проекта дополнительно возвращаются'
            ' контактные данные автора проекта.\n\n'
            ' - Доступно для аутентифицированного пользователя'
        ),
        examples=EXAMPLE_DETAIL_RESPONSE_PROJECT,
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
        """Возвращает список проектов с кэшированием списка ID."""
        user: Any = request.user
        query_params: Any = request.query_params

        sort_by: str = str(query_params.get('sort_by', ''))
        search_query: str = str(query_params.get('search', ''))
        is_relevance: bool = (
            'relevance' in sort_by and len(search_query) > 0
        )

        cache_key: Optional[str] = None
        if not is_relevance:
            cache_key = _build_list_cache_key(
                prefix=CACHE_KEY_PROJECTS_PREFIX,
                user=user,
                query_params=query_params,
            )

        logger.info(
            'Запрос списка проектов: user_id=%s, role=%s, params=%s, '
            'cache_key=%s',
            user.pk if user.is_authenticated else 'anonymous',
            (
                user.projects_relation
                if user.is_authenticated
                else 'anonymous'
            ),
            query_params,
            cache_key,
        )

        if cache_key is None and not is_relevance:
            logger.info(
                'Кэширование списка проектов отключено: user=anonymous',
            )
            return super().list(request, *args, **kwargs)

        ordered_ids: List[str] = []

        if cache_key is None:
            filtered_queryset = self.filter_queryset(self.get_queryset())
            ordered_ids = [
                str(project_id)
                for project_id in filtered_queryset.values_list(
                    'project_id',
                    flat=True,
                )
            ]
        else:
            cached_ids: Optional[List[str]] = cache.get(cache_key)
            if cached_ids is None:
                filtered_queryset = self.filter_queryset(self.get_queryset())
                ordered_ids = [
                    str(project_id)
                    for project_id in filtered_queryset.values_list(
                        'project_id',
                        flat=True,
                    )
                ]
                cache.set(
                    cache_key,
                    ordered_ids,
                    timeout=PROJECT_LIST_CACHE_TIMEOUT,
                )
                logger.info(
                    'Cache MISS: key=%s, total_ids=%d',
                    cache_key,
                    len(ordered_ids),
                )
            else:
                ordered_ids = cached_ids
                logger.info(
                    'Cache HIT IDs: key=%s, total_ids=%d',
                    cache_key,
                    len(ordered_ids),
                )

        page_ids: Optional[List[str]] = self.paginate_queryset(
            ordered_ids,
        )

        if not page_ids:
            logger.debug(
                'Страница списка проектов пуста: page=%d',
                self.paginator.page.number,
            )
            return self.get_paginated_response([])

        preserved_order: Case = Case(
            *[
                When(project_id=project_id, then=Value(position))
                for position, project_id in enumerate(page_ids)
            ],
            output_field=IntegerField(),
        )

        page_queryset = (
            self.get_queryset()
            .filter(project_id__in=page_ids)
            .order_by(preserved_order)
        )

        page_queryset.query.extra_order_by = ()
        page_queryset.query.default_ordering = False

        serializer: Any = self.get_serializer(
            page_queryset,
            many=True,
        )

        logger.debug(
            'Список проектов сформирован: cache_status=%s, '
            'page=%d, page_size=%d, total_ids=%d',
            'HIT' if cache_key and cached_ids is not None else 'MISS',
            self.paginator.page.number,
            len(page_ids),
            len(ordered_ids),
        )

        return self.get_paginated_response(serializer.data)

    def get_queryset(self) -> QuerySet[Project]:
        """Оптимизированный queryset с предзагрузкой связанных данных.

        Аннотирует is_liked_by_me, is_participant, participants_count,
        likes_count через подзапросы на уровне БД.

        Логика видимости в зависимости от action вынесена в selectors:
        - list (без my_project): get_visible_projects_for_list
        - retrieve: get_visible_projects_for_retrieve
        """
        user = self.request.user
        qs = get_optimized_project_queryset(user=user)
        if self.action == 'list':
            my_project = self.request.query_params.get('my_project')
            if not my_project or my_project.lower() == 'false':
                # Если применена фильтрация по специализации (spec_id),
                # скрываем проекты с закрытым набором (recruiting_closed).
                has_spec_filter = bool(
                    self.request.query_params.getlist('spec_id'),
                )
                qs = get_visible_projects_for_list(
                    qs,
                    exclude_recruiting_closed=has_spec_filter,
                )
            return qs
        if self.action == 'retrieve':
            return get_visible_projects_for_retrieve(qs, user)
        if self.action in ('partial_update', 'favorite'):
            return exclude_archived_blocked(qs)
        if self.action == 'destroy':
            return qs.exclude(status_project=BLOCKED)
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
        logger.info(
            'Проект успешно создан: user_id=%s, project_id=%s',
            request.user.pk,
            project.project_id,
        )
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
            'Запрос на "мягкое удаление" проекта: project=%s, user=%s.',
            project.project_id,
            request.user,
        )
        archive_project(project, user=request.user)
        logger.info(
            'Изменен статус проекта на "archive": project=%s, user=%s.',
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
                    'или проект с текущим статусом (draft, blocked).'
                ),
            ),
            404: OpenApiResponse(
                description='Проект не найден.',
            ),
        },
    )
    @action(detail=True, methods=['post'], url_path='like')
    @transaction.atomic
    def like(self, request: Request, *args: Any, **kwargs: Any) -> DRFResponse:
        """Эндпоинт для постановки/снятия лайка проекту."""
        project = self.get_object()
        is_liked_before = ProjectLike.objects.filter(
            project=project,
            user=request.user,
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
            'Статус лайка для проекта изменён: project_id=%s, user_id=%s, '
            'liked=%s',
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
        parameters=PROJECT_RECOMENDATIONS_PARAMETERS,
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
    )
    @action(detail=False, methods=['get'], url_path='recommendations')
    def recommendations(
        self,
        request: Request,
    ) -> DRFResponse:
        """Вернуть страницу рекомендаций из кэшированного списка ID."""
        user = request.user
        cache_key = _build_recommendations_cache_key(request)
        logger.debug(
            'Запрос персональных рекомендаций: user_id=%s, cache_key=%s',
            user.pk,
            cache_key,
        )
        cached_ids = cache.get(cache_key)

        if cached_ids is None:
            recommended_projects = get_recommended_projects_queryset(user)
            ordered_ids = [
                str(project_id)
                for project_id in recommended_projects.values_list(
                    'project_id',
                    flat=True,
                )
            ]
            cache.set(
                cache_key,
                ordered_ids,
                timeout=PROJECT_RECOMMENDATIONS_CACHE_TIMEOUT,
            )
            logger.debug(
                'Cache MISS рекомендаций: user_id=%s, total_ids=%d',
                user.pk,
                len(ordered_ids),
            )
        else:
            ordered_ids = cached_ids
            logger.debug(
                'Cache HIT рекомендаций: user_id=%s, total_ids=%d',
                user.pk,
                len(ordered_ids),
            )

        page_ids = self.paginate_queryset(ordered_ids)
        if not page_ids:
            return self.get_paginated_response([])

        preserved_order = Case(
            *[
                When(project_id=project_id, then=position)
                for position, project_id in enumerate(page_ids)
            ],
            output_field=IntegerField(),
        )
        page_queryset = (
            get_optimized_project_queryset(user)
            .filter(project_id__in=page_ids)
            .order_by(preserved_order)
        )
        serializer = ProjectShortSerializer(
            page_queryset,
            many=True,
            context={'request': request},
        )
        logger.debug(
            'Рекомендации сформированы: cache_status=%s, page=%d, '
            'page_size=%d, total_ids=%d',
            'HIT' if cached_ids is not None else 'MISS',
            self.paginator.page.number,
            len(page_ids),
            len(ordered_ids),
        )
        return self.get_paginated_response(serializer.data)

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
            project.project_id,
            request.user.pk,
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
