from typing import Any, Type

from django.core.cache import cache
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
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from core.constants.cache import (
    CACHE_KEY_SKILLS_PREFIX,
    CACHE_KEY_SPECIALIZATIONS_PREFIX,
    CACHE_KEY_WORK_FORMATS_PREFIX,
    TAGS_CACHE_TIMEOUT,
)
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
    """View для получения списков тегов.
    (Skills, Specializations, WorkFormats).
    """

    permission_classes: tuple[Type[BasePermission], ...] = (AllowAny,)

    def get_tag_type(self) -> str:
        """Извлечь path-параметр."""
        return self.kwargs.get('tag_type', '').lower()

    def _get_cache_key_prefix(self) -> str:
        """Возвращает префикс ключа кэша в зависимости от типа тега."""
        tag_type: str = self.get_tag_type()
        if tag_type == 'skills':
            return CACHE_KEY_SKILLS_PREFIX
        if tag_type == 'spec':
            return CACHE_KEY_SPECIALIZATIONS_PREFIX
        if tag_type == 'format':
            return CACHE_KEY_WORK_FORMATS_PREFIX
        return ''

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

    def list(self, request, *args, **kwargs):
        """Кэширует список тегов.

        Ключ: {prefix}:list, TTL 1 час.
        (skills:list / specializations:list / work_formats:list)
        """
        cache_key_prefix = self._get_cache_key_prefix()
        if not cache_key_prefix:
            return super().list(request, *args, **kwargs)

        cache_key = f'{cache_key_prefix}:list'

        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=TAGS_CACHE_TIMEOUT,
            )

        return response
