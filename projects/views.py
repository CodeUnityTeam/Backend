from typing import Any, List

from django.db import transaction
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
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
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import ProjectFilter
from .models import Project
from .paginations import CustomProjectPagination
from .permissions import CanArchiveProject
from .selectors import get_project_or_404
from .serializers import (
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
)


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
)
class ProjectViewSet(ModelViewSet):
    """Вьюсет для работы с проектами."""

    permission_classes = (IsAuthenticated,)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProjectFilter
    pagination_class = CustomProjectPagination
    lookup_field = 'project_id'

    def get_queryset(self) -> QuerySet[Project]:
        """Оптимизированный queryset с предзагрузкой связанных данных."""
        return Project.objects.select_related(
            'author',
        ).prefetch_related(
            'skills',
            'specializations',
            'project_format',
            'participants',
            'likes',
            'responses',
        )

    def get_permissions(self) -> List[BasePermission]:
        """Переопределяем разрешения для разных действий.

        - Для list — AllowAny, для остальных — стандартные.
        """
        if self.action == 'list':
            return [AllowAny()]
        if self.action == 'destroy':
            return [CanArchiveProject()]
        return super().get_permissions()

    def filter_queryset(
        self,
        queryset: QuerySet[Project],
    ) -> QuerySet[Project]:
        """Применяет фильтрацию только для действия list."""
        if self.action == 'list':
            for backend in list(self.filter_backends):
                queryset = backend().filter_queryset(
                    self.request,
                    queryset,
                    self,
                )
        return queryset

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Динамический выбор сериализатора в зависимости от действия."""
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        if self.action == 'create':
            return ProjectCreateSerializer
        if self.action == 'destroy':
            return ProjectArchiveSerializer
        if self.action == 'list':
            return ProjectShortSerializer
        if self.action == 'like':
            return ProjectLikeSerializer
        if self.action == 'partial_update':
            return ProjectUpdateSerializer
        if self.action == 'responses':
            return ResponseResponseCreateProjectSerializer
        return ProjectDetailSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Создание проекта."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        return Response(
            ProjectCreationResponseSerializer(project).data,
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Переводит проект в статус 'archived'. (мягкое удаление).

        - Доступ только для автора проекта и админов.
        """
        project = get_project_or_404(kwargs.get('pk'))
        serializer = self.get_serializer(
            instance=project,
            context={'request': request},
        )
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
            tags=['Проекты'],
            summary='Лайк/снятие лайка проекта',
        )
    @action(detail=True, methods=['post'], url_path='like')
    @transaction.atomic
    def like(self, request: Request, pk: str | None = None) -> Response:
        """Эндпоинт для постановки/снятия лайка проекту."""
        project = self.get_object()
        input_serializer = ProjectLikeSerializer(
            data={'project_id': project.project_id},
            context={'request': request, 'project': project},
        )
        input_serializer.is_valid(raise_exception=True)
        result = input_serializer.toggle_like()
        return Response(
            ProjectLikeResponseSerializer(result).data,
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Обновление проекта, возможно  частичное."""
        project = self.get_object()
        serializer = self.get_serializer(
            instance=project,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        response_serializer = ProjectUpdateResponseSerializer(project)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

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
    ) -> Response:
        """Эндпоинт для отклика пользователя на проект."""
        project = get_project_or_404(project_id=project_id)
        serializer = ResponseUserProjectSerializer(
            data={},
            context={'request': request, 'project': project},
        )
        serializer.is_valid(raise_exception=True)
        response = serializer.save()
        return Response(
            ResponseResponseCreateProjectSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )
