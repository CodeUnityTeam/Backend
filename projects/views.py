from typing import Any, List

from django.db import transaction
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status
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
    ProjectShortSerializer,
)


class ProjectViewSet(ModelViewSet):
    """Вьюсет для работы с проектами."""

    queryset = Project.objects.all()
    permission_classes = (IsAuthenticated,)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ProjectFilter
    pagination_class = CustomProjectPagination

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
