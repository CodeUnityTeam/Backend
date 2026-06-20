from typing import Any, Type

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


@extend_schema_view(
    list=extend_schema(
        tags=['Отклики'],
        summary='Лента откликов/приглашений',
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

    def get_serializer_context(self) -> dict[str, Any]:
        """Добавить user в контекст сериализатора."""
        context = super().get_serializer_context()
        context['user'] = self.request.user
        return context


class ProjectResponseViewSet(GenericViewSet):
    """Вьюсет для откликов и приглашений в контексте проекта.

    - create (POST): откликнуться на проект — только worker.
    - invite (POST): пригласить пользователя — только employer-автор.
    """

    permission_classes = (IsAuthenticated,)
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
            return [IsWorker()]
        if self.action == 'invite':
            return [IsEmployer()]
        return [permission() for permission in self.permission_classes]

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
        serializer = self.get_serializer(data={})
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
        """Пригласить пользователя в проект (только для employer-автора)."""
        serializer = self.get_serializer(data={})
        serializer.is_valid(raise_exception=True)
        response_instance = serializer.save()
        return DRFResponse(
            ResponseResponseCreateProjectSerializer(
                response_instance,
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
    serializer_class = UpdateResponseStatusResponseSerializer
    lookup_field = 'response_id'

    def get_queryset(self) -> QuerySet:
        """Базовый queryset откликов с оптимизацией запросов.

        Загружает project__author и user через select_related
        для валидации прав (project.author, user_response.user).
        """
        return get_response_for_status_update_queryset()

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
