import hashlib
import logging
from typing import Any, Type

from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response as DRFResponse
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from core.constants.cache import (
    CACHE_KEY_RESPONSES_PREFIX,
    RESPONSE_FEED_CACHE_TIMEOUT,
)
from projects.filters import ResponseFeedFilter
from projects.paginations import CustomResponseFeedPagination
from projects.permissions import IsEmployer, IsWorker
from projects.selectors import (
    get_project_for_response_queryset,
    get_response_feed_queryset,
    get_response_for_status_update_queryset,
)
from projects.serializers import (
    FeedbackAndInvitationFeedSerializer,
    InviteUserProjectSerializer,
    ResponseResponseCreateProjectSerializer,
    ResponseUserProjectSerializer,
    UpdateResponseStatusResponseSerializer,
    UpdateResponseStatusSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=['Отклики'],
        summary='Лента откликов/приглашений',
        description=(
            'Лента откликов/приглашений с фильтрацией и пагинацией.\n\n'
            'Эндпоинт доступен только работнику (worker).\n\n'
            'Пользователь видит свои отклики на проекты.\n\n'
            ' - Имеется фильтрация по ID-проекта;\n\n'
            ' - Имеется фильтрация по статусу отклика;\n\n'
            ' - Имеется сортировка по убыванию или возрастанию.\n\n'
        ),
        parameters=[
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
                name='sort_order',
                description=(
                    'Порядок сортировки по created_at.\n\n'
                    'Допустимые значения:\n\n'
                    '  • "asc" — по возрастанию (старые сначала)\n\n'
                    '  • "desc" — по убыванию (новые сначала).\n\n'
                    'По умолчанию — "desc".'
                ),
                required=False,
                type=str,
                enum=['asc', 'desc'],
                location=OpenApiParameter.QUERY,
            ),
        ],
    ),
)
class ResponseFeedViewSet(ListModelMixin, GenericViewSet):
    """Лента откликов/приглашений.

    Предоставляет единый список откликов и приглашений
    для текущего пользователя с фильтрацией и пагинацией.
    Доступен только для пользователей с ролью worker.
    """

    permission_classes = (IsWorker,)
    pagination_class = CustomResponseFeedPagination
    serializer_class = FeedbackAndInvitationFeedSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ResponseFeedFilter

    def get_queryset(self) -> QuerySet:
        """Базовый queryset для ленты откликов текущего пользователя."""
        return get_response_feed_queryset(self.request.user)

    def list(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Лента откликов/приглашений с фильтрацией и пагинацией.

        Ключ: responses:feed:{user_id}:{md5(params)}, TTL 3 мин.
        """
        query_params = request.query_params.dict()
        sorted_params = sorted(query_params.items())
        params_str = hashlib.md5(str(sorted_params).encode()).hexdigest()
        cache_key = (
            f'{CACHE_KEY_RESPONSES_PREFIX}:feed:'
            f'{request.user.pk}:{params_str}'
        )
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(
                'Кэшированный ответ для ленты откликов/приглашений: '
                'user_id=%s, cache_key=%s.',
                request.user.pk,
                cache_key,
            )
            return DRFResponse(cached_response)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            cache.set(
                cache_key,
                response.data,
                timeout=RESPONSE_FEED_CACHE_TIMEOUT,
            )
            logger.debug(
                'Лента откликов/приглашений выдана из БД: user_id=%s.',
                request.user.pk,
            )
        return response


class ProjectResponseViewSet(GenericViewSet):
    """Вьюсет для откликов и приглашений в контексте проекта.

    - create (POST): откликнуться на проект — только worker.
    - invite (POST): пригласить пользователя — только employer-автор.
    """

    permission_classes = (IsAuthenticated(),)
    lookup_field = 'project_id'
    serializer_class = ResponseUserProjectSerializer

    def get_queryset(self) -> QuerySet:
        """Оптимизированный queryset проекта для откликов/приглашений.

        Загружает author через select_related для валидации прав
        (project.author == user) без дополнительного запроса.
        """
        return get_project_for_response_queryset()

    def get_serializer_class(self) -> Type[Serializer]:
        """Применяем сериализатор в зависимости от action."""
        if self.action == 'create':
            return ResponseUserProjectSerializer
        if self.action == 'invite':
            return InviteUserProjectSerializer
        return self.serializer_class

    def get_serializer_context(self) -> dict[str, Any]:
        """Добавить project и user_id в контекст сериализатора."""
        context = super().get_serializer_context()
        context['project'] = self.get_object()
        if self.action == 'invite':
            context['user_id'] = self.kwargs.get('user_id')
        return context

    def get_permissions(self) -> list:
        """Динамические permission в зависимости от action."""
        if self.action == 'create':
            return (IsWorker(),)
        if self.action == 'invite':
            return (IsEmployer(),)
        return self.permission_classes

    @extend_schema(
        tags=['Отклики'],
        summary='Откликнуться на проект',
        request=None,
    )
    @transaction.atomic
    def create(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Откликнуться на проект (только для worker)."""
        logger.info(
            'Получен запрос на создание отклика: user_id=%s, project_id=%s.',
            request.user.pk,
            kwargs['project_id'],
        )
        serializer = self.get_serializer(data={})
        serializer.is_valid(raise_exception=True)
        response = serializer.save()
        logger.info(
            'Отклик на проект успешно создан: '
            'user_id=%s, project_id=%s, response_id=%s',
            request.user.pk,
            kwargs['project_id'],
            response.pk,
        )
        return DRFResponse(
            ResponseResponseCreateProjectSerializer(
                response,
                context={'request': request},
            ).data,
            status=status.HTTP_200_OK,
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
    @transaction.atomic
    def invite(
        self,
        request: Request,
        project_id: str,
        user_id: str,
    ) -> DRFResponse:
        """Пригласить пользователя в проект (только для employer-автора)."""
        logger.info(
            'Получен запрос на приглашение пользователя в проект: '
            'employer=%s, invited=%s, project_id=%s.',
            request.user.pk,
            user_id,
            project_id,
        )
        serializer = self.get_serializer(data={})
        serializer.is_valid(raise_exception=True)
        response_instance = serializer.save()
        logger.info(
            'Приглашение на проект успешно отправлено: '
            'employer=%s, invited=%s, project_id=%s, response_id=%s',
            request.user.pk,
            user_id,
            project_id,
            response_instance.pk,
        )
        return DRFResponse(
            ResponseResponseCreateProjectSerializer(
                response_instance,
                context={'request': request},
            ).data,
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    update=extend_schema(
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
                summary='Пользователь отзывает свой отклик',
                description='Пользователь отменяет свой отклик на проект',
                value={'status': 'withdrawn'},
                request_only=True,
                response_only=False,
            ),
            OpenApiExample(
                name='Принять отклик',
                summary='Пользователь одобряет отклик',
                description='Пользователь одобряет отклик',
                value={'status': 'approved'},
                request_only=True,
                response_only=False,
            ),
            OpenApiExample(
                name='Отклонить отклик',
                summary='Пользователь отклоняет отклик',
                description='Пользователь отклоняет отклик',
                value={'status': 'rejected'},
                request_only=True,
                response_only=False,
            ),
        ],
    ),
)
class ResponseStatusViewSet(GenericViewSet):
    """Вьюсет для изменения статуса отклика/приглашения."""

    permission_classes = (IsAuthenticated,)
    serializer_class = UpdateResponseStatusResponseSerializer
    lookup_field = 'response_id'

    def get_queryset(self) -> QuerySet:
        """Базовый queryset откликов с оптимизацией запросов.

        Загружает project__author и user через select_related
        для валидации прав (project.author, user_response.user).
        """
        return get_response_for_status_update_queryset()

    @extend_schema(
        request=UpdateResponseStatusSerializer,
        responses={200: UpdateResponseStatusSerializer},
    )
    @transaction.atomic
    def update(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Изменить статус отклика/приглашения.

        Учитываем права и статусы отклика.
        - Наниматель (employer) может отклонить, одобрять отклики только от
         работников. Может отозвать свой отклик.
        - Работник (worker) может отклонить, одобрять отклики только от
         нанимателя. Может отозвать свой отклик.
        """
        response = self.get_object()
        old_status = response.status_resp
        logger.info(
            'Получен запрос на изменение статуса отклика/приглашения: '
            'user_id=%s, projects_relation=%s, project_id=%s, '
            'response_id=%s.',
            request.user.pk,
            request.user.projects_relation,
            response.project.pk,
            response.pk,
        )
        serializer = UpdateResponseStatusSerializer(
            instance=response,
            data=request.data,
            context={'request': request},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        update_status = serializer.save()
        logger.info(
            'Статус отклика/приглашения успешно изменен: '
            'user_id=%s, projects_relation=%s, project_id=%s, '
            'response_id=%s, old_status=%s, new_status=%s.',
            request.user.pk,
            request.user.projects_relation,
            response.project.pk,
            response.pk,
            old_status,
            update_status.status_resp,
        )
        return DRFResponse(
            self.get_serializer(update_status).data,
            status=status.HTTP_200_OK,
        )
