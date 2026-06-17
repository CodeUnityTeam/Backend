from typing import Any, Type

from django.db.models import QuerySet
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.serializers import BaseSerializer

from projects.models import WorkFormat
from projects.serializers import (
    SkillSerializer,
    SpecializationSerializer,
    WorkFormatSerializer,
)
from users.models.skills import Skill
from users.models.specializations import Specialization


@extend_schema_view(
    get=extend_schema(
        summary='Получение списка тегов',
        description=(
            'Возвращает список элементов в зависимости от переданного '
            'в пути параметра `tag_type` (навыки, специализации или '
            'форматы работы).'
        ),
        parameters=[
            OpenApiParameter(
                name='tag_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Тип тегов: 'skills', 'spec' или 'format'",
                enum=['skills', 'spec', 'format'],
            ),
        ],
        responses={
            200: PolymorphicProxySerializer(
                component_name='TagsList',
                serializers={
                    'skills': SkillSerializer,
                    'spec': SpecializationSerializer,
                    'format': WorkFormatSerializer,
                },
                resource_type_field_name=None,
                many=True,
            ),
            400: OpenApiResponse(
                description='Неверный параметр tag_type в пути',
                examples={
                    'error': {
                        'summary': 'Ошибка валидации',
                        'value': {
                            'detail': "Неподдерживаемый тип тега: 'unknown'",
                        },
                    },
                },
            ),
        },
    ),
)
class TagsListAPIView(ListAPIView):
    """View для получения списков тегов."""

    permission_classes: tuple[Type[BasePermission], ...] = (AllowAny,)

    def get_tag_type(self) -> str:
        """Извлечь path-параметр."""
        return self.kwargs.get('tag_type', '').lower()

    def get_serializer_class(self) -> Type[BaseSerializer]:
        """Динамически выбрать сериализатор на основе path-параметра."""
        tag_type: str = self.get_tag_type()

        if tag_type == 'skills':
            return SkillSerializer
        if tag_type == 'spec':
            return SpecializationSerializer
        if tag_type == 'format':
            return WorkFormatSerializer

        raise ValidationError(f"Неподдерживаемый тип тега: '{tag_type}'")

    def get_queryset(self) -> QuerySet[Any]:
        """Динамически выбрать queryset на основе path-параметра."""
        tag_type: str = self.get_tag_type()

        if tag_type == 'skills':
            return Skill.objects.all()
        if tag_type == 'spec':
            return Specialization.objects.all()
        if tag_type == 'format':
            return WorkFormat.objects.all()

        return Skill.objects.none()
