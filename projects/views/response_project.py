import hashlib
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response as DRFResponse
from rest_framework.viewsets import GenericViewSet

from core.constants.cache import (
    CACHE_KEY_RESPONSES_PREFIX,
    RESPONSE_FEED_CACHE_TIMEOUT,
)
from projects.filters import ResponseFeedFilter
from projects.models import Project, Response
from projects.paginations import CustomResponseFeedPagination
from projects.selectors import (
    get_response_feed_queryset,
)
from projects.serializers import (
    FeedbackAndInvitationFeedSerializer,
    InviteUserProjectSerializer,
    ResponseResponseCreateProjectSerializer,
    ResponseUserProjectSerializer,
    UpdateResponseStatusSerializer,
)


@extend_schema_view(
    list=extend_schema(
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
    ),
)
class ResponseFeedViewSet(GenericViewSet):
    """Вьюсет для ленты откликов/приглашений.

    Предоставляет единый список откликов и приглашений
    для текущего пользователя с фильтрацией и пагинацией.
    """

    permission_classes = (IsAuthenticated,)
    pagination_class = CustomResponseFeedPagination
    serializer_class = FeedbackAndInvitationFeedSerializer

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
        user = request.user
        query_params = request.query_params.dict()
        sorted_params = sorted(query_params.items())
        params_str = hashlib.md5(
            str(sorted_params).encode(),
        ).hexdigest()
        cache_key = (
            f'{CACHE_KEY_RESPONSES_PREFIX}:feed:'
            f'{user.pk}:{params_str}'
        )

        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return DRFResponse(cached_response)

        queryset = self.get_queryset()
        filterset = ResponseFeedFilter(
            request.GET,
            queryset=queryset,
            request=request,
        )
        filtered_queryset = filterset.qs
        paginator = self.pagination_class()
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
            response = paginator.get_paginated_response(serializer.data)
        else:
            response = DRFResponse(serializer.data)
            response.data['applied_filters'] = {
                'card_type': request.query_params.get('card_type', 'all'),
                'status': request.query_params.get('status', 'all'),
            }

        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=RESPONSE_FEED_CACHE_TIMEOUT,
            )

        return response


class ProjectResponseViewSet(GenericViewSet):
    """Вьюсет для откликов и приглашений в контексте проекта."""

    permission_classes = (IsAuthenticated,)
    lookup_field = 'project_id'
    serializer_class = ResponseResponseCreateProjectSerializer

    def get_queryset(self) -> QuerySet:
        """Базовый queryset не используется — проект получаем напрямую."""
        return Project.objects.all()

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
        """Откликнуться на проект."""
        project = self.get_object()
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
    @transaction.atomic
    def invite(
        self,
        request: Request,
        project_id: str,
        user_id: str,
    ) -> DRFResponse:
        """Пригласить пользователя в проект."""
        project = self.get_object()
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
                summary='Пример: пользователь отзывает свой отклик',
                description='Пользователь отменяет свой отклик на проект',
                value={'status': 'withdrawn'},
                request_only=True,
                response_only=False,
            ),
        ],
    ),
)
class ResponseStatusViewSet(GenericViewSet):
    """Вьюсет для изменения статуса отклика/приглашения."""

    permission_classes = (IsAuthenticated,)
    serializer_class = ResponseResponseCreateProjectSerializer
    lookup_field = 'response_id'

    def get_queryset(self) -> QuerySet:
        """Базовый queryset откликов."""
        return Response.objects.all()

    @transaction.atomic
    def update(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> DRFResponse:
        """Изменить статус отклика/приглашения."""
        response = self.get_object()
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
