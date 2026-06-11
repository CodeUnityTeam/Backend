import uuid
from typing import Any

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
)
from django.core.files.uploadedfile import UploadedFile
from django.db.models import QuerySet
from django.http import HttpRequest
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from config import settings
from users.models.users import User, UserExperience
from users.pagination import ProfileListPagination
from users.serializers.profile import (
    AvatarUploadSerializer,
    CustomUserDetailsSerializer,
    DetailUserProfileSerializer,
    PublicUserProfileSerializer,
    UserExperienceSerializer,
)
from users.services import avatar_delete_handler, avatar_upload_handler

UserModel = get_user_model()


# ============================== MeProfile ===================================

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
    delete=extend_schema(
        tags=['profile'],
        summary='Мягкое удаление аккаунта текущего пользователя',
        description=(
            'Переводит флаги is_active и is_agreed_to_terms в False. '
            'Пользователь деактивируется, но запись в БД сохраняется.'
        ),
        request=None,
        responses={
            200: inline_serializer(
                name='CurrentUserDeleteSuccessResponse',
                fields={
                    'detail': serializers.CharField(
                        default='Аккаунт успешно удален.',
                    ),
                },
            ),
            401: inline_serializer(
                name='CurrentUserDeleteUnauthorizedResponse',
                fields={
                    'detail': serializers.CharField(
                        default='Учетные данные не были предоставлены.',
                    ),
                },
            ),
        },
    ),
)
class MeProfileView(RetrieveUpdateDestroyAPIView):
    """View для работы с профилем авторизованного пользователя.

    Поддерживает просмотр, редактирование и мягкое удаление.
    """

    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Вернуть объект текущего авторизованного пользователя."""
        return self.request.user

    def perform_destroy(self, instance: User) -> None:
        """Перевести флаги активности и согласия в False."""
        instance.is_active = False
        instance.is_agreed_to_terms = False
        instance.save()

        EmailAddress.objects.filter(
            user=instance,
            email__iexact=instance.email,
        ).update(verified=False)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Мягко далить аккаунт и вернуть статус HTTP 200 с сообщением."""
        self.destroy(request, *args, **kwargs)
        return Response(
            {"detail": "Аккаунт успешно удален."},
            status=status.HTTP_200_OK,
        )


# ================================== Avatar ===================================

@extend_schema_view(
    post=extend_schema(
        summary="Загрузить аватар пользователя",
        description=(
            "Загрузка изображения (jpeg, jpg, png) размером до 10 МБ. "
            "Старый файл аватара автоматически удаляется из MinIO."
        ),
        request={
            "multipart/form-data": inline_serializer(
                name="AvatarUploadRequest",
                fields={
                    "file": serializers.ImageField(help_text="Файл аватара"),
                },
            ),
        },
        responses={
            status.HTTP_201_CREATED: inline_serializer(
                name="AvatarUploadResponse",
                fields={"avatar_url": serializers.URLField()},
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
        },
        tags=["Files"],
    ),
    delete=extend_schema(
        summary="Удалить аватар пользователя",
        description=(
            "Удаляет файл аватара из хранилища MinIO и "
            "очищает поле avatar_url в профиле пользователя."
        ),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
        },
        tags=["Files"],
    ),
)
class UserAvatarAPIView(APIView):
    """API view для загрузки и удаления аватара пользователя."""

    permission_classes: list[type[IsAuthenticated]] = [IsAuthenticated]
    parser_classes: list[type[MultiPartParser]] = [MultiPartParser]
    allow_upload_size: int = settings.ALLOW_AVATAR_SIZE_MB * 1024 * 1024

    def post(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> Response:
        """Загрузить новый аватар и удалить старый при наличии."""
        serializer: AvatarUploadSerializer = AvatarUploadSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        user: User = request.user  # type: ignore[valid-type]
        file_obj: UploadedFile = serializer.validated_data["file"]

        public_url: str = avatar_upload_handler(user, file_obj)

        return Response(
            {"avatar_url": public_url}, status=status.HTTP_201_CREATED,
        )

    def delete(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> Response:
        """Удаленить аватар."""
        user: User = request.user  # type: ignore[valid-type]

        if not user.avatar_url:
            return Response(
                {"detail": "Аватар отсутствует."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avatar_delete_handler(user)

        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================ Experience =================================

@extend_schema_view(
    create=extend_schema(
        tags=['profile'],
        summary='Добавить запись об опыте работы',
        responses={201: UserExperienceSerializer},
    ),
    update=extend_schema(
        tags=['profile'],
        summary='Полностью обновить запись своего опыта',
        responses={200: UserExperienceSerializer},
    ),
    destroy=extend_schema(
        tags=['profile'],
        summary='Удалить запись своего опыта',
        responses={204: None},
    ),
)
class MeExperienceViewSet(ModelViewSet):
    """Управление опытом работы текущего авторизованного пользователя.

    Исключает метод PATCH, оперирует только своими записями.
    """

    serializer_class = UserExperienceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['post', 'put', 'delete']

    def get_queryset(self) -> QuerySet[UserExperience]:
        """Возвращает опыт работы только текущего пользователя."""
        return UserExperience.objects.filter(user=self.request.user)

    def perform_create(self, serializer: UserExperienceSerializer) -> None:
        """Автоматически привязывает опыт к текущему пользователю."""
        serializer.save(user=self.request.user)


# ============================== UserProfile ==================================

@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля неавторизованного пользователя',
        description='Данные доступны по ID пользователя.',
        responses={200: DetailUserProfileSerializer},
    ),
)
class UserProfileView(RetrieveAPIView):
    """View для просмотра профиля пользователя по ID."""

    queryset = UserModel.objects.filter(is_active=True)
    serializer_class = DetailUserProfileSerializer
    permission_classes = [IsAuthenticated]


# =============================== ListProfile =================================

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
        queryset = UserModel.objects.filter(is_active=True).prefetch_related(
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
