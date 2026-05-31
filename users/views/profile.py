import uuid
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
)
from django.db.models import QuerySet
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.permissions import IsAuthenticated

from users.models.users import User
from users.pagination import ProfileListPagination
from users.serializers.profile import (
    CustomUserDetailsSerializer,
    PublicUserProfileSerializer,
)

UserModel = get_user_model()


@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля авторизованного пользователя',
        responses={200: CustomUserDetailsSerializer},
    ),
    patch=extend_schema(
        tags=['profile'],
        summary='Частично обновить данные авторизованного пользователя',
        request=CustomUserDetailsSerializer,
        responses={200: CustomUserDetailsSerializer},
    ),
)
class MeProfileView(RetrieveUpdateAPIView):
    """View просмотра и редактирования профиля авторизованного пользователя."""

    http_method_names = ['get', 'patch', 'head', 'options']
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Возвращает объект текущего авторизованного пользователя."""
        return self.request.user


@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля неавторизованного пользователя',
        description='Данные доступны по ID пользователя.',
        responses={200: PublicUserProfileSerializer},
    ),
)
class UserProfileView(RetrieveAPIView):
    """View для просмотра профиля неавторизованного пользователяпо ID."""

    queryset = UserModel.objects.all()
    serializer_class = PublicUserProfileSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить список профилей пользователей',
        description=(
            'Возвращает пагинированный список публичных профилей с фильтрацией'
            ' по специализациям, навыкам, текстовым поиском и сортировкой. '
            'Все параметры не обязательны.'
        ),
        parameters=[
            OpenApiParameter(
                name='spec_id',
                type=str,
                required=False,
                location=OpenApiParameter.QUERY,
                description='Список ID специализаций через запятую (UUID).',
            ),
            OpenApiParameter(
                name='skill_id',
                type=str,
                required=False,
                location=OpenApiParameter.QUERY,
                description='Список ID навыков через запятую (UUID).',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                required=False,
                location=OpenApiParameter.QUERY,
                description='Поиск по имени, фамилии, стране или городу.',
            ),
            OpenApiParameter(
                name='sort_by',
                type=str,
                required=False,
                location=OpenApiParameter.QUERY,
                enum=['newest', 'relevance'],
                description=(
                    'Сортировка: newest (по умолчанию) или relevance (только '
                    'при наличии search).',
                ),
            ),
        ],
        responses={200: PublicUserProfileSerializer(many=True)},
    ),
)
class UserProfileListView(ListAPIView):
    """View для получения списка профилей пользователей."""

    serializer_class = PublicUserProfileSerializer
    pagination_class = ProfileListPagination
    permission_classes = [IsAuthenticated]

    def _parse_and_validate_uuids(self, raw_string: str | None) -> list[str]:
        """Распарсить строку через запятую и оставить только валидные UUID."""
        if not raw_string:
            return []

        valid_uuids = []
        for item in raw_string.split(','):
            cleaned = item.strip()
            try:
                uuid.UUID(cleaned)
                valid_uuids.append(cleaned)
            except ValueError:
                continue
        return valid_uuids

    def _apply_search_and_sorting(
        self, queryset: QuerySet[Any],
        search_query: str,
        sort_by: str,
    ) -> QuerySet[Any]:
        """Применить полнотекстовый поиск PostgreSQL и условную сортировку."""
        if search_query:
            vector = (
                SearchVector('first_name', weight='A')
                + SearchVector('last_name', weight='A')
                + SearchVector('country', weight='B')
                + SearchVector('city', weight='B')
            )
            query = SearchQuery(search_query)
            queryset = queryset.annotate(
                rank=SearchRank(vector, query),
            ).filter(rank__gt=0.0)

            if sort_by == 'relevance':
                return queryset.order_by('-rank', '-created_at')

        return queryset.order_by('-created_at')

    def get_queryset(self) -> QuerySet[Any]:
        """Получить QuerySet с учетом поиска и фильтров."""
        queryset = UserModel.objects.prefetch_related(
            'specializations',
            'skills',
        )

        # Извлекаем параметры
        spec_str = self.request.query_params.get('spec_id')
        skill_str = self.request.query_params.get('skill_id')
        search_query = self.request.query_params.get('search', '').strip()
        sort_by = self.request.query_params.get('sort_by', 'newest')

        # Фильтруем M2M связи
        spec_ids = self._parse_and_validate_uuids(spec_str)
        if spec_ids:
            queryset = queryset.filter(
                specializations__spec_id__in=spec_ids,
            ).distinct()

        skill_ids = self._parse_and_validate_uuids(skill_str)
        if skill_ids:
            queryset = queryset.filter(
                skills__skill_id__in=skill_ids,
            ).distinct()

        # Применяем поиск и сортировку
        return self._apply_search_and_sorting(queryset, search_query, sort_by)
